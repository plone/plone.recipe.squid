This repository is archived and read only.

If you want to unarchive it, then post to the [Admin & Infrastructure (AI) Team category on the Plone Community Forum](https://community.plone.org/c/aiteam/55).

Squid recipe for buildout
===========================

Inspired by plone.recipe.varnish, plone.recipe.squid is a `zc.buildout`_ 
recipe to install `Squid`_. 

Even though the name contains "plone" there is nothing Plone specific about
this recipe: it works with non-Zope sites just as well.

Configuration is very simple. For example::

    [squid-build]
    recipe = zc.recipe.cmmi
    url = http://www.squid-cache.org/Versions/v2/2.7/squid-2.7.STABLE5.tar.gz

    [squid-instance]
    recipe = plone.recipe.squid
    daemon = ${squid-build:location}/sbin/squid
    bind = 127.0.0.1:3128
    backends = 127.0.0.1:8080
    cache-size = 1000

This configures two buildout parts: squid-build which will download,
compile and install Squid and squid-instance which runs Squid, configured to
listen on 127.0.0.1:3128 for requests, using a 1 gigabyte cache and sending
requests to a backend at 127.0.0.1:8080.

Wrappers for the Squid commands are created in the bin directory
of your buildout.

To start up Squid: ./bin/squid-instance

To shutdown Squid: ./bin/squid-instance -k shutdown


Virtual hosting
---------------

Squid supports virtual hosting by selecting a different backend server
based on headers on the incoming request. You can configure the backends
through the backends option::

  [squid-instance]
  backends =
     plone.org:127.0.0.1:8000
     plone.net:127.0.0.1:9000

This will generate a configuration which sends all traffic for the plone.org
host to a backend server running on port 8000 while all traffic for the
plone.net host is sent to port 9000.


Zope 2 hosting (with Virtual Host Monster)
-------------------------------------------

If you are using Zope 2 as backend server you will need to rewrite the URL
so the Zope Virtual Host Monster (VHM) can generate correct links for links in
your pages. This can be done by another web proxy such as Apache or nginx
(placed either in front or behind Squid) but can also be done by Squid itself.

The three options are described below.

Option 1 (rewrites after Squid):

If generating these VHM-style URLs in a proxy *behind* Squid (or if using
VHM's 'mapping' feature), no extra Squid configuration is needed.  
Just make sure the "backends" option directs the traffic to the proxy.

Option 2 (rewrites before Squid):

If generating these VHM-style URLs in a proxy *in-front* of Squid, no extra
Squid configuration is needed as long as the original hostname is still retained
in the URL. If the hostname is not retained, you can tell Squid to direct requests
based on the "path" instead of the hostname.  For example::

  [squid-instance]
  backends =
    /VirtualHostBase/http/plone.org:80/Plone:127.0.0.1:8000
    /VirtualHostBase/http/plone.net:80/Plone:127.0.0.1:9000

This will generate a configuration which sends all traffic for any request whose
path starts with "/VirtualHostBase/http/plone.org:80/Plone" to a backend server
running at 127.0.0.1 on port 8000, while request paths starting with 
"/VirtualHostBase/http/plone.net:80/Plone" are sent to port 9000.

Option 3 (rewrites within Squid):

To have Squid generate these VHM-style URLs, you can use the **zope2_vhm_map** option. 
Here is an example::

  [squid-instance]
  zope2_vhm_map =
      plone.org:/plone
      plone.net:/plone

This tells us that the domain plone.org should be mapped to the location
/plone in the backend. By combining this with the information from the
**backends** option a squid configuration will be generated that
maps URLs correctly.  Note: The 'zope2_vhm_map' option assumes delegation
by 'host' so do not try to combine options 2 and 3 within the same config.


plone.recipe.squid:build reference
------------------------------------

*The "build" recipe is obsolete and will be removed. Please use zc.recipe.cmmi instead*

The plone.recipe.squid:build recipe takes care of downloading Squid,
compiling it on your system and installing it in your buildout.

It can be configured with any of these options:

url
    URL for an archive containing the Squid sources. Either **url** or
    **svn** has to be specified.

svn
    URL for a subversion repository containing Squid sources. Either **url**
    or **svn** has to be specified.

squid-directory
    The location of a shared Squid installation directory.  Useful when
    building multiple Squid instances.  A shared Squid build can be stored
    separate from the buildout instance.  This directive must be defined in
    ~/.buildout/default.cfg similar to the "zope-directory" and "eggs-directory"
    directives.  The default is to build Squid in a subfolder of the buildout
    'parts' directory.

Please note that the configuration generated by this recipe requires
Squid 2.6.STABLE18 or later.  It is not tested with Squid 3.x.


plone.recipe.squid reference
---------------------------------------

The plone.recipe.squid recipe creates a Squid configuration
file and creates a wrapper script inside your buildout that will start
Squid with the correct configuration.

Please note that Squid does not support spaces in path names so this
recipe will not work if your buildout path contains any spaces.

Also note that the configuration generated by this recipe requires
Squid 2.6.STABLE18 or later.  It is not tested with Squid 3.x.


Squid-specific Configuration Options:

default-hostname
    The default hostname to use if request is missing the Host header.
    Only needed if delegating to backend by Host header and there is the
    possibility of requests coming in from old or buggy clients.  Defaults
    to the first hostname listed under 'backends'.

visible-hostname
    The hostname to show in squid-generated error pages.  Defaults either
    to a hostname if specified by 'bind' or, if not, then to the value 
    of 'default-hostname' 

visible-email
    The email address to show in squid-generated error pages.


General Configuration Options:

daemon
    The path of the squid daemon to use. Defaults to 'bin/squid' inside
    your buildout directory.

cache-size
    The size of the cache in MB. Do not exceed 90% of available disk
    space. Defaults to 1000 MB.

bind
    Hostname and port on which Squid will listen for requests.
    Syntax is [hostname][:port].  Defaults to 127.0.0.1:3128.
    If hostname is omitted then Squid will bind to all available
    interfaces.

config
    Path for a Squid config file to use. If you use this option
    you can not use the backends or zope2_vhm_map options.

backends
    Specifies the backend or backends which will process the (uncached)
    requests. The syntax for backends:
    
    [<hostname>][/<path>]:<ip address>:<port>
    
    The optional 'hostname' and 'path' allows you to do virtual hosting.
    If multiple backends are specified then each backend must include
    either a hostname or path (or both) so that Squid can direct the
    matching request to the appropriate backend. Defaults to 127.0.0.1:8080.

zope2_vhm_map
    Defines a virtual host mapping for Zope servers. This is a list of
    **hostname:ZODB location** entries which specify the location inside
    Zope where the website for a virtual host lives.

user
    The name of the user squid should switch to before accepting any
    requests. Defaults to 'squid'.

group
    The name of the group squid should switch to before accepting any
    request. This defaults to the main group for the specified user.


Reporting bugs or asking questions
----------------------------------

A shared bugtracker and help desk is available on Launchpad:
https://bugs.launchpad.net/collective.buildout/


.. _Squid: http://squid-cache.org/
.. _zc.buildout: http://cheeseshop.python.org/pypi/zc.buildout

