import logging
import os
import setuptools
import shutil
import string
import sys
import subprocess
import tempfile
import urllib2
import urlparse
import zc.buildout


class BuildRecipe:
    def __init__(self, buildout, name, options):
        self.name=name
        self.options=options
        self.buildout=buildout
        self.logger=logging.getLogger(self.name)

        self.svn=options.get("svn", None)
        self.url=options.get("url", None)
        if not (self.svn or self.url):
            self.logger.error(
                    "You need to specify either a URL or subversion repository")
            raise zc.buildout.UserError("No download location given")

        # If we use a download, then look for a shared Squid installation directory
        if self.svn is None and buildout['buildout'].get('squid-directory') is not None:
            _, _, urlpath, _, _, _ = urlparse.urlparse(self.url)
            fname = urlpath.split('/')[-1]
            # cleanup the name a bit
            for s in ('.tar', '.bz2', '.gz', '.tgz'):
                fname = fname.replace(s, '')
            location = options['location'] = os.path.join(
                buildout['buildout']['squid-directory'],fname)
            options['shared-squid'] = 'true'
        else:
            # put it into parts
            location = options['location'] = os.path.join(
                buildout['buildout']['parts-directory'],self.name)
        
        options["source-location"]=os.path.join(location, "source")
        options["binary-location"]=os.path.join(location, "install")
        options["daemon"]=os.path.join(options["binary-location"], "squid")

        # Set some default options
        buildout['buildout'].setdefault('download-directory',
                os.path.join(buildout['buildout']['directory'], 'downloads'))


    def install(self):
        self.installSquid()
        self.addScriptWrappers()
        if self.url and self.options.get('shared-squid') == 'true':
            # If the squid installation is shared, only return non-shared paths 
            return self.options.created()
        return self.options.created(self.options["location"])


    def update(self):
        pass


    def installSquid(self):
        location=self.options["location"]
        if os.path.exists(location):
            # If the squid installation exists and is shared, then we are done
            if self.options.get('shared-squid') == 'true':
                return
            else:
                shutil.rmtree(location)
        os.mkdir(location)
        self.downloadSquid()
        self.compileSquid()


    def downloadSquid(self):
        download_dir=self.buildout['buildout']['download-directory']

        if self.svn:
            self.logger.info("Checking out squid from subversion.")
            assert os.system("svn co %s %s" % (self.options["svn"], self.options["source-location"]))==0
        else:
            self.logger.info("Downloading squid tarball.")
            if not os.path.isdir(download_dir):
                os.mkdir(download_dir)

            _, _, urlpath, _, _, _ = urlparse.urlparse(self.url)
            tmp=tempfile.mkdtemp("buildout-"+self.name)

            try:
                fname=os.path.join(download_dir, urlpath.split("/")[-1])
                if not os.path.exists(fname):
                    f=open(fname, "wb")
                    try:
                        f.write(urllib2.urlopen(self.url).read())
                    except:
                        os.remove(fname)
                        raise
                    f.close()

                setuptools.archive_util.unpack_archive(fname, tmp)

                files=os.listdir(tmp)
                shutil.move(os.path.join(tmp, files[0]), self.options["source-location"])
            finally:
                shutil.rmtree(tmp)



    def compileSquid(self):
        os.chdir(self.options["source-location"])
        self.logger.info("Compiling Squid")
        
        #if self.svn:
        #    assert subprocess.call(["./autogen.sh"]) == 0
        
        assert subprocess.call(["./configure", "--prefix=" + self.options["binary-location"]]) == 0
        
        assert subprocess.call(["make", "install"]) == 0


    def addScriptWrappers(self):
        bintarget=self.buildout["buildout"]["bin-directory"]

        for dir in ["sbin"]:
            dir=os.path.join(self.options["binary-location"], dir)
            if not os.path.isdir(dir):
                continue
            for file in os.listdir(dir):
                self.logger.info("Adding script wrapper for %s" % file)
                target=os.path.join(bintarget, file)
                f=open(target, "wt")
                print >>f, "#!/bin/sh"
                print >>f, 'exec %s "$@"' % os.path.join(dir, file)
                f.close()
                os.chmod(target, 0755)
                self.options.created(target)


class ConfigureRecipe:
    def __init__(self, buildout, name, options):
        self.name=name
        self.options=options
        self.buildout=buildout
        self.logger=logging.getLogger(self.name)

        self.options["location"] = os.path.join(
                buildout["buildout"]["parts-directory"], self.name)

        # Set some default options
        self.options["bind"]=self.options.get("bind", "127.0.0.1:3128")
        self.options["cache-size"]=self.options.get("cache-size", 1000)
        self.options["daemon"]=self.options.get("daemon", 
                os.path.join(buildout["buildout"]["bin-directory"], "squid"))
        if self.options.has_key("config"):
            if self.options.has_key("backends") or \
                    self.options.has_key("zope2_vhm_map"):
                self.logger.error("If you specify the config= option you can "
                                  "not use backends or zope2_vhm_map.")
                raise zc.buildout.UserError("Can not use both config and "
                                           "backends or zope2_vhm_map options.")
            self.options["generate_config"]="false"
        else:
            self.options["generate_config"]="true"
            self.options["backends"]=self.options.get("backends", "127.0.0.1:8080")
            self.options["config"]=os.path.join(self.options["location"],"squid.conf")

        # Convenience settings
        (host,port)=self.options["bind"].split(":")
        self.options["bind-host"]=host
        self.options["bind-port"]=port

    def install(self):
        location=self.options["location"]

        if not os.path.exists(location):
            os.mkdir(location)
        self.options.created(location)

        self.addSquidRunners()
        if self.options["generate_config"]=="true":
            if self.options.get("zope2_vhm_map", None) is None:
                self.createSquidConfig()
            else:
                self.createSquidConfigVHM()

        return self.options.created()


    def update(self):
        pass


    def addSquidRunners(self):
        # build squid-initialize
        target=os.path.join(self.buildout["buildout"]["bin-directory"],'squid-initialize')
        f=open(target, "wt")
        print >>f, "#!/bin/sh"
        print >>f, 'exec %s -z \\' % self.options["daemon"]
        print >>f, '  -f %s  \\' % self.options["config"]
        print >>f, '  "$@"'
        f.close()
        os.chmod(target, 0755)
        self.options.created(target)

        # build squid-start
        target1=os.path.join(self.buildout["buildout"]["bin-directory"],'squid-start')
        f=open(target1, "wt")
        print >>f, "#!/bin/sh"
        print >>f, 'exec %s   \\' % self.options["daemon"]
        print >>f, '  -f %s \\' % self.options["config"]
        print >>f, '  "$@"'
        f.close()
        os.chmod(target1, 0755)
        self.options.created(target1)

        # build squid-stop
        target2=os.path.join(self.buildout["buildout"]["bin-directory"],'squid-stop')
        f=open(target2, "wt")
        print >>f, "#!/bin/sh"
        print >>f, 'exec %s -k shutdown \\' % self.options["daemon"]
        print >>f, '  -f %s \\' % self.options["config"]
        print >>f, '  "$@"'
        f.close()
        os.chmod(target2, 0755)
        self.options.created(target2)

        # build squid-purge
        target=os.path.join(self.buildout["buildout"]["bin-directory"],'squid-purge')
        f=open(target, "wt")
        print >>f, "#!/bin/sh"
        print >>f, 'echo "Stopping squid..."'
        print >>f, '%s' % target2
        print >>f, 'sleep 10'
        print >>f, 'echo "Clearing the cache..."'
        print >>f, 'echo "" > %s' % os.path.join(self.options["location"],"cache","swap.state")
        print >>f, 'echo "Starting squid..."'
        print >>f, '%s' % target1
        print >>f, 'echo "Done."'
        print >>f, ""
        print >>f, "# Note: Removal of swap.state to 'clear' the cache is not officially supported."
        print >>f, "# For now it works but there is no guarantee this will be the case in the future."
        f.close()
        os.chmod(target, 0755)
        self.options.created(target)


    def createSquidConfig(self):
        module = ''
        for x in self.options["recipe"]:
            if x in (':', '>', '<', '='):
                break
            module += x
        
        whereami=sys.modules[module].__path__[0]
        template=open(os.path.join(whereami, "template.conf")).read()
        template=string.Template(template)
        config={}

        backends=self.options["backends"].strip().split()
        backends=[x.rsplit(":",2) for x in backends]
        if len(backends)>1:
            lengths=set([len(x) for x in backends])
            if lengths!=set([3]):
                self.logger.error("When using multiple backends a hostname (or path) "
                                  "must be given for each client")
                raise zc.buildout.UserError("Multiple backends without hostnames/paths")

        zope_servers=['127.0.0.1']
        cache_peers=""
        cache_peer_access=""
        default_hostname = None
        for i in range(len(backends)):
            parts=backends[i]
            if len(parts)==2:
                if len(backends)==1:
                    if parts[0] not in zope_servers:
                        zope_servers.append(parts[0])
                    cache_peers+='cache_peer %s parent %s 0 no-query originserver login=PASS name=server_%s\n' % (parts[0], parts[1], i)
                    cache_peer_access+='cache_peer_access server_%s allow all\n' % i
                else:
                    self.logger.error("Invalid syntax for backend when multiple backends are defined: %s" % ":".join(parts))
                    raise zc.buildout.UserError("Invalid syntax for backends")
            elif len(parts)==3:
                if parts[1] not in zope_servers:
                    zope_servers.append(parts[1])
                cache_peers+='cache_peer %s parent %s 0 no-query originserver login=PASS name=server_%s\n' % (parts[1], parts[2], i)
                if parts[0].startswith('/'):
                    cache_peer_access+='acl path_%s urlpath_regex %s\n' % (i, parts[0])
                    cache_peer_access+='cache_peer_access server_%s allow path_%s' % (i, i)
                    cache_peer_access+='cache_peer_access server_%s deny all' % i
                else:
                    if default_hostname is None:
                        default_hostname=parts[0]
                    cache_peer_access+='cache_peer_domain server_%s %s' % (i, parts[0])
            else:
                self.logger.error("Invalid syntax for backend: %s" % ":".join(parts))
                raise zc.buildout.UserError("Invalid syntax for backends")

        # Allow buildout config to override the default hostname.
        # If we're still missing a default hostname, let's create a dummy one.
        # Not sure if this is necessary but it doesn't hurt.
        if self.options.get("default_hostname", None) is not None:
            default_hostname = self.options.get("default_hostname")
        if default_hostname is None:
            default_hostname = 'example.com'

        # Figure out the visible hostname for squid error pages
        visible_hostname=self.options.get("visible_hostname", None)
        if visible_hostname is None:
            if self.options['bind-host'].split('.')[-1].isalpha():
                visible_hostname = self.options['bind-host']
            else:
                visible_hostname = default_hostname

        # visible email for squid error pages
        visible_email=self.options.get("visible_email", '')
        if visible_email != '':
            visible_email = 'cache_mgr %s\n' % visible_email

        # user / group
        user=self.options.get("user", None)
        group=self.options.get("group", None)
        usergroup = ''
        if user is not None:
            usergroup = 'cache_effective_user %s\n' % user
            if group is not None:
                usergroup += 'cache_effective_group %s\n' % group


        config["zope_servers"]=' '.join(zope_servers)
        config["cache_peers"]=cache_peers
        config["cache_peer_access"]=cache_peer_access
        config["default_hostname"]=default_hostname
        config["visible_hostname"]=visible_hostname
        config["visible_email"]=visible_email
        config["usergroup"]=usergroup
        config["bind"]=self.options.get("bind")
        config["bind_host"]=self.options.get("bind-host")
        config["bind_port"]=self.options.get("bind-port")
        config["location"]=self.options["location"]
        config["cache_size"]=self.options["cache-size"]


        f=open(self.options["config"], "wt")
        f.write(template.safe_substitute(config))
        f.close()
        self.options.created(self.options["config"])


    def createSquidConfigVHM(self):
        module = ''
        for x in self.options["recipe"]:
            if x in (':', '>', '<', '='):
                break
            module += x
        
        whereami=sys.modules[module].__path__[0]
        template=open(os.path.join(whereami, "template-vhm.conf")).read()
        template=string.Template(template)
        templates = ['iRedirector.py','redirector_class.py']
        config={}

        zope2_vhm_map=self.options.get("zope2_vhm_map", "").split()
        zope2_vhm_map=dict([x.split(":") for x in zope2_vhm_map])

        backends=self.options["backends"].strip().split()
        backends=[x.rsplit(":",2) for x in backends]
        if len(backends)>1:
            lengths=set([len(x) for x in backends])
            if lengths!=set([3]):
                self.logger.error("When using multiple backends a hostname (or path) "
                                  "must be given for each client")
                raise zc.buildout.UserError("Multiple backends without hostnames/paths")

        zope_servers=['127.0.0.1']
        sitemap=""
        default_hostname = None
        for i in range(len(backends)):
            parts=backends[i]
            if len(parts)==2:
                if len(backends)==1:
                    if parts[0] not in zope_servers:
                        zope_servers.append(parts[0])
                    sitemap+="(10, '[\S]*'): '%s:%s/VirtualHostBase/http/${HTTP_HOST}:80%s/VirtualHostRoot',\n" % (
                               parts[0], parts[1], zope2_vhm_map[0])
                else:
                    self.logger.error("Invalid syntax for backend when multiple backends are defined: %s" % ":".join(parts))
                    raise zc.buildout.UserError("Invalid syntax for backends")
            elif len(parts)==3:
                if parts[1] not in zope_servers:
                    zope_servers.append(parts[1])
                sitemap+="(10, '[\S]%s'): '%s:%s/VirtualHostBase/http/${HTTP_HOST}:80%s/VirtualHostRoot',\n" % (
                           parts[0], parts[1], parts[2], zope2_vhm_map[parts[0]])
                if parts[0].startswith('/'):
                    self.logger.error("Path prefix not allowed in backends when using zope2_vhm_map: %s" % ":".join(parts))
                    raise zc.buildout.UserError("Invalid syntax for backends")
                else:
                    if default_hostname is None:
                        default_hostname=parts[0]
            else:
                self.logger.error("Invalid syntax for backend: %s" % ":".join(parts))
                raise zc.buildout.UserError("Invalid syntax for backends")

        # Allow buildout config to override the default hostname.
        # If we're still missing a default hostname, let's create a dummy one.
        # Not sure if this is necessary but it doesn't hurt.
        if self.options.get("default_hostname", None) is not None:
            default_hostname = self.options.get("default_hostname")
        if default_hostname is None:
            default_hostname = 'example.com'

        # Figure out the visible hostname for squid error pages
        visible_hostname=self.options.get("visible_hostname", None)
        if visible_hostname is None:
            if self.options['bind-host'].split('.')[-1].isalpha():
                visible_hostname = self.options['bind-host']
            else:
                visible_hostname = default_hostname

        # visible email for squid error pages
        visible_email=self.options.get("visible_email", '')
        if visible_email != '':
            visible_email = 'cache_mgr %s\n' % visible_email

        # user / group
        user=self.options.get("user", None)
        group=self.options.get("group", None)
        usergroup = ''
        if user is not None:
            usergroup = 'cache_effective_user %s\n' % user
            if group is not None:
                usergroup += 'cache_effective_group %s\n' % group


        config["zope_servers"]=' '.join(zope_servers)
        config["sitemap"]=sitemap
        config["default_hostname"]=default_hostname
        config["visible_hostname"]=visible_hostname
        config["visible_email"]=visible_email
        config["usergroup"]=usergroup
        config["bind"]=self.options.get("bind")
        config["bind_host"]=self.options.get("bind-host")
        config["bind_port"]=self.options.get("bind-port")
        config["location"]=self.options["location"]
        config["cache_size"]=self.options["cache-size"]


        f=open(self.options["config"], "wt")
        f.write(template.safe_substitute(config))
        f.close()
        self.options.created(self.options["config"])

        for fname in templates:
            template = open(os.path.join(whereami, fname)).read()
            template = string.Template(template)
            target = os.path.join(self.options['location'], fname)
            f = open(target, "wt")
            f.write(template.safe_substitute(config))
            f.close()
            self.options.created(target)



