---
layout: post
title: Monogatari frame drops
date: 2016-04-06 15:05
---

# Monotatari frame drops

<video loop controls src="hitagi-drop.webm"><img src="hitagi-drop-000.png"></video>

There is a beatiful web page: [Monogatari drops][1],
and it's a rare example of an acceptable use
of page scroll for artistic purposes.

The page is great, I like the concept, I like the art,
I like monogatari series in general.

But there is a problem: the page is slow. And we're going to fix it.

# Measuring

When I said "the page is slow", I mean that the
page scrolling seems to drop frames.
But there should always be a way to measure how "slow" it is.

Let's look at Chrome's timeline report.

![chrome's profiler report for original page][2]

35 milliseconds for a frame?!

I'm viewing this page on a high-end PC,
capable of drawing millions of textured polygons per second,
and you say that it takes you 35 millisecond to update this page?

And the main culprit is this function:

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

This function is constantly causing layout updates by requesting `$scene.height()` and writing `$object.css(...)`.

If we cache `$scene` size in it's `data`, chrome won't have to update layout several times:

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

![chrome's profiler report for first fix][3]

8ms? Much better, but can we improve it?

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

This code is causing unnecessary layout update too, and has a similar fix:

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

This will call `show()` or `hide()` on *many* DOM nodes on *each* frame, which is unacceptable.

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

And another fix with layout request:

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

![chrome's profiler report for next fixes][4]

4ms? Can we do better? Maybe. But I'll call this good enough and enjoy my day.

But what about those frame drops?

![chrome's profiler showing cause of frame drops][5]

These frame drops are caused by images downloading and decoding additional images in background,
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

By default, this code will change Hitagi's frames as fast as possible (int my case, 60 fps).

But anime is usually animated at 12 fps, so we have to limit the frame rate:

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

*Finally*, I can enjoy this piece of art in silky smooth 60 fps.

Full patch with several bug fixes is available [here][6].

[1]: http://kodansha-box.jp/topics/nishio/drops/
[2]: timeline-original.png
[3]: timeline-fix-01.png
[4]: timeline-fix-02.png
[5]: timeline-fix-02-frame-drop.png
[6]: faster-monogatari-drops.diff
