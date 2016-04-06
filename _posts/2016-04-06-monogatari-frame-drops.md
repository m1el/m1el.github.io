---
layout: post
permalink: /monogatari-frame-drops/index.html
title: Monogatari frame drops
date: 2016-04-06 15:05
---

<video loop controls src="/monogatari-frame-drops/hitagi-drop.webm"><img src="/monogatari-frame-drops/hitagi-drop-000.png"></video>

There is a beatiful web page: [Monogatari drops][1],
and it's a rare example of an acceptable use
of page scroll for artistic purposes.

The page is great, I like the concept, I like the art,
I like monogatari series.

But there is a problem: the page is slow. And we're going to fix it.

An optimized and fixed version of the page os available over [here][7],
and more details on the optimization process are available in the rest of this post.

<!-- more -->
<style>@media screen and (min-width: 1100px) {
  img[src$="#sshot"] { max-width: none; margin-left: -173px; }
}</style>

# Measuring

When I said "the page is slow", I mean that the
page scrolling seems to drop frames.
But there should always be a way to measure how "slow" it is.

Let's look at Chrome's timeline report.

![Chrome's profiler report for original page][2]

35 milliseconds for a frame?!

I'm viewing this page on a high-end PC,
capable of drawing millions of textured polygons per second,
and you tell me it takes 35 millisecond to scroll?

If we look at the profile, we can easily identify the main culprit:

```javascript
$(document).on('scrolled', function(){
  if(
    $scroll_top + $window_height < $scene.data('offset_top') + $scene.height() &&
    $scroll_top > $scene.data('offset_top')
  ) {
    var translateY = size * (3 - (($scroll_top - $scene.data('offset_top')) / $window_height));
    $object.css({'transform': 'translateY(' + translateY + 'px) rotateZ(' + rotate + 'deg)'});
  }
});
```

# Layout thrashing

The browser can't return layout properties without re-calculating the layout,
if the layout has changed. This problem is known as *Layout thrashing*.

The function in question is constantly causing layout re-calculations by requesting `$scene.height()` and updating `$object.css(...)`.

If we cache `$scene`'s height in it's `data`, Chrome won't have to update the layout several times:

```diff
diff --git a/main-orig.js b/main.js
--- a/main-orig.js
+++ b/main.js
@@ -249,6 +249,7
       $(".scene").each(function(){
         var $scene = $(this);
         $scene.data('offset_top', $scene.offset().top);
+        $scene.data('height', $scene.height());
       });
     };
     fix_size();
@@ -284,7 +285,7
             var _num = parseInt($scene.attr('id').replace(/^[^\d]*(\d+)[^\d]*$/, "$1"), 10);
             if(
               $scroll_top > $scene.data('offset_top') &&
-              $scene.data('offset_top') + $scene.height() > $scroll_top &&
+              $scene.data('offset_top') + $scene.data('height') > $scroll_top &&
               scene_num !== _num
             ) {
               $(document).trigger('change_nav', _num);
@@ -660,7 +661,7

         $(document).on('scrolled', function(){
           if(
-            $scroll_top + $window_height < $scene.data('offset_top') + $scene.height() &&
+            $scroll_top + $window_height < $scene.data('offset_top') + $scene.data('height') &&
             $scroll_top > $scene.data('offset_top')
           ) {
             var translateY = size * (3 - (($scroll_top - $scene.data('offset_top')) / $window_height));
```

![Chrome's profiler report for first fix][3]

8 ms? Much better, but can we improve this?

The next culprit is:

```javascript
$(document).on('scrolled', function(){
  if(
    ($scroll_top + $window_height - 70) > $object.offset().top
  ) {
    if (($scroll_top + 300) > $object.offset().top + $object.height()){
      $object.removeClass('show');
    } else {
      $object.addClass('show');
      $object.trigger('show');
    }
  } else {
    $object.removeClass('show');
  }
});
```

This code is causing some unnecessary layout updates, and has a similar fix:

```diff
diff --git a/main-orig.js b/main.js
--- a/main-orig.js
+++ b/main.js
@@ -616,11 +623,13
             img1.src = "/content/topics/nishio/drops/imgs/scene/low/"+num+"_1.jpg";
             img2.src = "/content/topics/nishio/drops/imgs/scene/low/"+num+"_2.jpg";
           });
+          $object.data('offset_top', $object.offset().top);
+          $object.data('height', $object.height());
           $(document).on('scrolled', function(){
             if(
-              ($scroll_top + $window_height - 70) > $object.offset().top
+              ($scroll_top + $window_height - 70) > $object.data('offset_top')
             ) {
-              if (($scroll_top + 300) > $object.offset().top + $object.height()){
+              if (($scroll_top + 300) > $object.data('offset_top') + $object.data('height')){
                 $object.removeClass('show');
               } else {
                 $object.addClass('show');
```

The next slow function is:

```javascript
$(document).on('scrolled', function(){
  if( $scroll_top + $window_height > $scene.data('offset_top') && $scroll_top - 7.5 * $window_height < $scene.data('offset_top')  ) {
    $scene.data("objects").show();
  } else {
    $scene.data("objects").hide();
  }
});
```

This function will call `show()` or `hide()` on *many* DOM nodes on *each* frame,
which is a big performance hit.

The fix is pretty straightforward:

```javascript
var objectsVisible = null;
$(document).on('scrolled', function(){
  var newVisible = $scroll_top + $window_height > $scene.data('offset_top') &&
                   $scroll_top - 7.5 * $window_height < $scene.data('offset_top');
  if (objectsVisible !== newVisible) {
    if(newVisible) {
      $scene.data("objects").show();
    } else {
      $scene.data("objects").hide();
    }
    objectsVisible = newVisible;
  }
});
```

And another fix with layout thrashing:

```diff
diff --git a/main-fix1.js b/main.js
--- a/main-fix1.js
+++ b/main.js
@@ -251,6 +251,9 @@ function closeOpening () {
         $scene.data('offset_top', $scene.offset().top);
         $scene.data('height', $scene.height());
       });
+
+      var $ending_wrapper = $(".ending_wrapper");
+      $ending_wrapper.data('offset_top', $ending_wrapper.offset().top);
     };
     fix_size();
     $(window).resize(fix_size);
@@ -532,12 +535,12 @@ function closeOpening () {
         return false;
       };
       $(document).on('scrolled', function(){
-        if( $scroll_top > $ending_wrapper.offset().top ) {
+        if( $scroll_top > $ending_wrapper.data('offset_top') ) {
           $ending.css({ 'position': 'fixed' });
           // console.log(ending_player.getPlayerState());
           if( ending_player ) {
             if (ending_player.getPlayerState() === 1 || ending_player.getPlayerState() === -1) {
-              window.scrollTo(0, $ending_wrapper.offset().top);
+              window.scrollTo(0, $ending_wrapper.data('offset_top'));
               $ending
                 .on('mousewheel', stopevent)
                 .on('scroll', stopevent)
```

What do you think now, Mr. Profiler?

![Chrome's profiler report for next fixes][4]

4 ms? Can we do better? Maybe. But I'll call this good enough and enjoy my day.

What about those frame drops at the 5 second mark?

![Chrome's profiler showing cause of frame drops][5]

These frame drops are caused by downloading and decoding additional images in the background,
unfortunately we can't do much about it.

# Unwanted 60 fps

Surprisingly, there is a part of this page that needs to have a lower framerate: Hitagi animation.

```javascript
imgLoad.on('done', function(){
  var flag = true;
  $(document).on('scrolled', function(){
    cnt++;
    $hitagi_img.attr("src", images[cnt % images.length]);
  });
});
```

By default, this code will change Hitagi's frames as fast as possible. In my case, it runs at 60 fps, and looks ridiculous.

Anime is usually animated at 12 fps, so we have to limit the frame rate:

```javascript
var lastChange = 0;
imgLoad.on('done', function(){
  var flag = true;
  $(document).on('scrolled', function(){
    var now = Date.now();
    if (now - lastChange > 1000 / 12) {
      cnt++;
      lastChange = now;
      $hitagi_img.attr("src", images[cnt % images.length]);
    }
  });
});
```

# End

It's pretty impressive how such little things can make or break JS/HTML performance.

You can look at the optimized *Monogatari drops* over [here][7].

And full patch with several bug fixes is available [here][6].

Comments on [reddit][8]

*Finally*, I can enjoy this piece of art in silky smooth 60 fps.

[1]: http://kodansha-box.jp/topics/nishio/drops/
[2]: timeline-original.png#sshot
[3]: timeline-fix-01.png#sshot
[4]: timeline-fix-02.png#sshot
[5]: timeline-fix-02-frame-drop.png#sshot
[6]: faster-monogatari-drops.diff
[7]: http://m1el.github.io/nishio-drops
[8]: https://www.reddit.com/r/programming/comments/4dmivz/monogatari_frame_drops_a_writeup_on_js/
