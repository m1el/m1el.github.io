---
layout: post
permalink: /oculus-tls-extract/
title: Extracting TLS keys from an unwilling application
date: 2020-04-11 16:00
---

# Extracting TLS keys from an unwilling application

I want to be able to inspect the traffic of programs running on my computer.
I don't really trust those programs and ideally I'd like to put nearly all of them into a high security jail.

One of those programs is Oculus software.  There are a few reasons why I want to be cautious about Oculus software.

<!-- more -->

1. Oculus is owned by Facebook, which means Facebook *can* dictate what Oculus software does with user's data.
2. Oculus servers run on Facebook's infrastructure, which means that Facebook *can* have access to any data uploaded to those servers.
3. Oculus Headset has cameras and software that builds a 3D map of my room, which *can* be uploaded to the servers.
4. Oculus [oculus-pp][Privacy Policy] explicitly states that Oculus automatically collects:  
> Information about your environment, physical movements, and dimensions when you use an XR device.  For example, when you set up the Oculus Guardian System to alert you when you approach a boundary, we receive information about the play area that you have defined;

Fortunately, I can use programs such as Wireshark or tcpdump to inspect traffic sent to the servers.  
Fortunately, Oculus is using TLS so that a third party cannot snoop on this data in transit.  
Unfortunately, I am playing a role of "third party" in this case.  
Fortunately, it's possible to read process memory and extract secret keys and inspect TLS data.

## Things that didn't work

- Setting [`SSLKEYLOGFILE`][wireshark-tls] variable -- Oculus Runtime is using a 1.0.2o version of OpenSSL where this is not supported.  
- [Extracting OpenSSL keys using an automated debugger][openssl-gdb-python] -- Oculus Runtime is using statically linked OpenSSL with no debug symbols.
- Substituting OpenSSL library with one that can log secret keys -- it's statically linked.
- I didn't want to add extra root certificates and proxies to inspect all TLS traffic going on the machine. 

## Doing this the hard way

So the plan forward was to:

- Figure out a code location where secret keys for the session are available
- Patch or debug the program so that we can inspect and log those keys

## A bit of reverse engineering

To figure out the code location some reverse-engineering was necessary.  The first step was to figure out which version does Oculus Runtime use.  Looking for strings in `OculusAppFramework.dll`, there was the following string: `Stack part of OpenSSL 1.0.2o-fb10  27 Mar 2018`, which means I have a specific version that I work off.

After reading [Introduction to OpenSSL programming on Linux Journal][linux-journal-openssl], I deduced that `SSL_connect` (and later `SSL_set_connect_state`) may be a good place to interject OpenSSL for key extraction.

I've loaded up Oculus Runtime into Ghidra, opened up source code that contains public interface of OpenSSL `ssl_lib.c` and attempted to find common ground between those.  The things of interest were integer and string constants which could be used as landmarks.

A particularly notable function is `SSL_get_version`, which contains references to multiple strings.  Looking for `TLSv1.2` yielded a few locations, particularly this one:

![](inlined-ssl-get-version.png)

It looks like `SSL_get_version` got inlined.  I suspected that this was not the only place where TLS connections were made, so I had to find a different place to work on.  The next notable thing was that near one of the SSL version strings I've noticed code paths and assertion strings:

![](assertion-info.png)

As it turns out, debug information such as source file names and assetion expressions, which can be used as landmarks too.
Now we have more landmarks to navigate OpenSSL binary code.

I've continued to label function as I inspected nearby references to `.\\ssl\ssl_lib.c` strings, and I've stumbled onto [`SSL_set_connect_state` function](ssl-set-connect-ghidra.png).  Using the same code pattern, [`mov dword ptr [$register + 0x48], 0x5000`](code-pattern.png), I've found [`SSL_connect`](ssl-connect-ghidra.png) as well.  `SSL_connect` had an inlined call to `SSL_set_connect_state`.  I've decided to be cautious and interject both of these functions.

## Extracting the data

These functions already have pointers to `ssl_st` struct, so let's extract the data from there.

There were a few options to do this:
- Use/write a programmable debugger and breakpoint/inspect values on those functions
- Binary patch the DLL
- Use DLL injection and patching in-memory DLL code

Since I've had poor experience with controlling debuggers programmatically, I didn't want to go use the first option.  This is a potential thing that I might want to improve.
Since I didn't want to invalidate a signed DLL, I didn't binary patch it.
Last option it is.

## DLL injection

To extract *all* TLS keys, we need to control the running process from the very beginning.
One way to do this is to set `gflags` to use DLL injector program as a debugger for the process.
The program we want to debug is called `OVRServer_x64.exe`, so let's create `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\OVRServer_x64.exe` key in registry and set `Debugger` string value to command line of our injector.

The injector doesn't have to *do* any debugging, but it needs to start a program with `DEBUG_ONLY_THIS_PROCESS` or `DEBUG_PROCESS` flag.  Otherwise, our debugger will be [spawned recursively](recursive-injector-spawn.png).

The `CreateRemoteThread` DLL injection is itself a simple technique on Windows, it's consicely described in a [WikiLeaks article][wikileaks-dll-injection] as well in other articles.

The code for `injector.exe` is [here][ote-injector].

## Extracting the data

After the DLL was injected, it can patch the code in-memory and log secret keys.

The architecture for `injectee.dll` is pretty simple -- patch the code, create a channel, create writer thread with the receiving end of the channel, send keys from different threads using the other end.

Patching was done in assembly.  It can be approximately described like this:

![](asm-patch.png)

There are several ways to extract the keys ginen a pointer to `ssl_st` struct.
- Implementing a C library
- Walking the pointers manually
- Porting OpenSSL structs to the used language

Initially I've implemented walking the pointers by hand, but that is a very fragile approach.
Porting OpenSSL structs to Rust is quite cumbersome, so I've implemented a [miniature C library][ote-ssl-inspector] to read secret keys given an `ssl_st` struct pointer.

The rest is plumbing, and we now can inspect TLS traffic in a running application:

![](extracted-tls-keys.png)

The code for `injectee.dll` is [here][ote-injectee].

If you're interested, the entire code for the project is here: [github.com/m1el/oculus-tls-extractor](https://github.com/m1el/oculus-tls-extractor)

Analysis of the data being sent by Oculus Runtime to the mothership is coming up in the follow-up post.

[oculus-pp]: https://www.oculus.com/legal/privacy-policy/ "Oculus Privacy Policy (Last Updated: December 27, 2019)"
[wireshark-tls]: https://wiki.wireshark.org/TLS "Wireshark wiki: TLS"
[openssl-gdb-python]: https://security.stackexchange.com/questions/80158/extract-pre-master-keys-from-an-openssl-application "StackExchange: Extract pre-master keys from an OpenSSL application"
[mozilla-ssl-keylog]: https://developer.mozilla.org/en-US/docs/Mozilla/Projects/NSS/Key_Log_Format "MDN: NSS Key Log Format"
[linux-journal-openssl]: https://www.linuxjournal.com/article/4822 "An Introduction to OpenSSL Programming, Part I of II"
[wikileaks-dll-injection]: https://wikileaks.org/ciav7p1/cms/page_3375330.html "CreateRemoteThread DLL Injection"
[ote-injector]: https://github.com/m1el/oculus-tls-extractor/blob/master/injector.rs "Oculus TLS Extractor -- injector.rs"
[ote-injectee]: https://github.com/m1el/oculus-tls-extractor/blob/master/injectee.rs "Oculus TLS Extractor -- injectee.rs"
[ote-ssl-inspector]: https://github.com/m1el/oculus-tls-extractor/blob/master/ssl_inspector.c "Oculus TLS Extractor -- ssl_inspector.c"
