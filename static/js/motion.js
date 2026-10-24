/* Motion layer — Lenis smooth scrolling + GSAP scroll reveals.

   Libraries are self-hosted in static/js/vendor (nothing points at a CDN at
   render time, same as the rest of the project). Everything here is
   progressive enhancement: with the libraries missing, under
   prefers-reduced-motion, or on the chat shell, the page behaves exactly as it
   did before — the reveal targets are below the fold and fully visible without
   any of this. The restrained house style means the motion stays quiet:
   smooth scroll, and one gentle rise-and-fade as a block scrolls in. */
(function () {
    'use strict';

    var reduce = window.matchMedia &&
                 window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) return;

    var hasGSAP = typeof window.gsap !== 'undefined' &&
                  typeof window.ScrollTrigger !== 'undefined';
    var hasLenis = typeof window.Lenis !== 'undefined';
    // The chat page is a fixed app shell with its own scroll areas, so the
    // window barely scrolls — smoothing it there only adds lag.
    var isChat = document.body.classList.contains('body--chat');

    var lenis = null;
    if (hasLenis && !isChat) {
        lenis = new window.Lenis({
            duration: 1.05,
            easing: function (t) { return Math.min(1, 1.001 - Math.pow(2, -10 * t)); },
            smoothWheel: true,
            smoothTouch: false
        });
    }

    if (hasGSAP) {
        window.gsap.registerPlugin(window.ScrollTrigger);

        // Drive Lenis from GSAP's ticker and keep ScrollTrigger in step with
        // its virtual scroll position (the standard integration).
        if (lenis) {
            lenis.on('scroll', window.ScrollTrigger.update);
            window.gsap.ticker.add(function (time) { lenis.raf(time * 1000); });
            window.gsap.ticker.lagSmoothing(0);
        }

        // gsap.from sets the hidden start state only when GSAP runs, so without
        // JS the blocks are simply visible; and they live below the hero, so
        // the hidden start is off-screen at load — no flash of content.
        window.gsap.utils.toArray('.rail-section, [data-reveal]').forEach(function (el) {
            window.gsap.from(el, {
                opacity: 0,
                y: 26,
                duration: 0.7,
                ease: 'power2.out',
                scrollTrigger: { trigger: el, start: 'top 85%', once: true }
            });
        });
    } else if (lenis) {
        // Smooth scroll without GSAP: Lenis needs its own animation loop.
        (function raf(time) { lenis.raf(time); requestAnimationFrame(raf); })();
    }
})();
