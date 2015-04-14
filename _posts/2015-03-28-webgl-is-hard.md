---
layout: post
title: WebGL is hard
date: 2015-03-28 10:09
---

I spent a whole day debugging [Bezier SDF shader][1] only to find out that [WebGL is broken in the browser][2]

Don't even ask me how I managed to find a workaround in the form of `if (abs(s) > 0.) {}` for Chrome.

[1]: https://www.shadertoy.com/view/Mlj3zD
[2]: /images/webgl-shaders-browsers.png
