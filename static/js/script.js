function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function appendChatBubble(thread, role, text) {
    const bubble = document.createElement('div');
    bubble.className = `ai-chat-bubble ${role}`;
    bubble.textContent = text;
    thread.appendChild(bubble);
    thread.scrollTop = thread.scrollHeight;
    return bubble;
}

async function typeMentorResponse(data) {
    const thread = document.getElementById('ai-chat-thread');
    if (!thread || !data || !Array.isArray(data.teaching_guide)) {
        return;
    }

    const stepsBubble = appendChatBubble(thread, 'assistant', '');
    const tipBubble = appendChatBubble(thread, 'assistant tip', '');
    const stepLines = data.teaching_guide.slice(0, 3);

    for (let index = 0; index < stepLines.length; index += 1) {
        const prefix = index === 0 ? '' : '\n';
        for (const char of prefix + stepLines[index]) {
            stepsBubble.textContent += char;
            await sleep(12);
        }
        await sleep(120);
    }

    const fullTip = `Mentor tip: ${data.mentor_tip}`;
    for (const char of fullTip) {
        tipBubble.textContent += char;
        await sleep(10);
    }
}

/*
   Removed: the "magic" effects layer — a cyan two-axis grid that swept the
   viewport, a burst of spark particles, and twenty-five music notes floating
   up the screen — which the AI assistant fired after every answer.

   None of it belonged to this product. HandShake moves parcels between towns;
   DESIGN.md's system is deep ink on paper with one warm note and no
   decoration that is not structural. The effects were also the loudest
   generated-UI signature left in the codebase. The assistant now simply
   answers, which is what it is for.
*/

async function fetchExpertData(itemQuery, question) {
    const response = await fetch('/api/expert', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            item_query: itemQuery,
            question: question
        })
    });

    const source = response.headers.get('X-Expert-Source') || 'unknown';
    const liveProviderAvailable = response.headers.get('X-Live-Provider-Available') === 'true';
    const payload = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(payload.error || 'Expert request failed');
    }
    return { data: payload, source: source, liveProviderAvailable: liveProviderAvailable };
}

function initExpertChat() {
    const sidebar = document.getElementById('ai-expert-sidebar');
    const launcher = document.getElementById('ai-expert-launcher');
    const closeButton = document.getElementById('ai-expert-close');
    const form = document.getElementById('ai-expert-form');
    const input = document.getElementById('ai-expert-input');
    const submitButton = form ? form.querySelector('button[type="submit"]') : null;
    const thread = document.getElementById('ai-chat-thread');
    const status = sidebar ? sidebar.querySelector('.ai-expert-status') : null;

    if (!sidebar || !launcher || !form || !input || !thread || !submitButton) {
        return;
    }

    const itemQuery = (sidebar.dataset.expertQuery || '').trim();
    let isLoading = false;

    function openSidebar() {
        sidebar.classList.add('visible');
        launcher.classList.add('hidden');
        input.focus();
    }

    function closeSidebarIfEmpty() {
        sidebar.classList.remove('visible');
        launcher.classList.remove('hidden');
    }

    async function ask(question) {
        if (!itemQuery || !question || isLoading) {
            return;
        }

        isLoading = true;
        openSidebar();
        appendChatBubble(thread, 'user', question);
        if (status) {
            status.textContent = 'AI is thinking...';
        }
        submitButton.disabled = true;
        input.disabled = true;

        try {
            const result = await fetchExpertData(itemQuery, question);
            const data = result.data;
            /* The panel used to take its accent from data.brand_color, with a
               teal fallback — an arbitrary hue injected at runtime into a
               system that is monochrome plus one warm note. It now stays in
               the palette like everything else. */
            if (status) {
                status.textContent = result.source === 'fallback'
                    ? (result.liveProviderAvailable
                        ? 'Answer ready - live providers did not respond in time, using fallback'
                        : 'Answer ready - no live API key is configured on the server, using fallback')
                    : `Answer ready - source: ${result.source}`;
            }
            await typeMentorResponse(data);
        } catch (error) {
            appendChatBubble(thread, 'assistant error', error.message || 'AI could not answer that right now.');
            if (status) {
                status.textContent = 'Request failed';
            }
        } finally {
            isLoading = false;
            submitButton.disabled = false;
            input.disabled = false;
            thread.scrollTop = thread.scrollHeight;
            input.focus();
        }
    }

    launcher.addEventListener('click', openSidebar);
    if (closeButton) {
        closeButton.addEventListener('click', closeSidebarIfEmpty);
    }
    document.addEventListener('click', (event) => {
        if (!sidebar.classList.contains('visible')) {
            return;
        }
        const clickedInsideSidebar = sidebar.contains(event.target);
        const clickedLauncher = launcher.contains(event.target);
        if (!clickedInsideSidebar && !clickedLauncher) {
            closeSidebarIfEmpty();
        }
    });

    sidebar.querySelectorAll('.ai-quick-action').forEach((button) => {
        button.addEventListener('click', () => {
            ask(button.dataset.expertQuestion || '');
        });
    });

    form.addEventListener('submit', (event) => {
        event.preventDefault();
        const question = input.value.trim();
        if (!question) {
            return;
        }
        input.value = '';
        ask(question);
    });

    input.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closeSidebarIfEmpty();
        }
    });
}

/* An earlier broken-image handler lived here. It registered before the one in
   PICTURES THAT DO NOT ARRIVE at the foot of this file and set the same
   dataset flag, so it always won the race and the designed fallback — the
   ruled hatch on a listing card, the drawn initials on an avatar — never ran.
   One handler, at the bottom. */

document.addEventListener('DOMContentLoaded', () => {
    /* The splash used to hold for 3.5s and fade for another 0.8s — over four
       seconds of a covered screen on every single navigation, which is a long
       time to be shown a logo you have already seen. It holds for 1.2s now.

       Clearing it also flips a flag on <html>. The hero's flight is paused
       until that flag appears, because the whole animation used to run and
       finish underneath the splash: it played to an audience of nobody. */
    const splash = document.getElementById('splash-screen');
    const revealPage = () => document.documentElement.classList.add('splash-done');
    if (splash) {
        setTimeout(() => {
            splash.classList.add('fade-out');
            revealPage();
            setTimeout(() => {
                splash.style.display = 'none';
            }, 800);
        }, 1200);
    } else {
        revealPage();
    }

    const themeBtn = document.getElementById('theme-toggle');
    const html = document.documentElement;
    if (themeBtn) {
        const themeIcon = themeBtn.querySelector('use');
        const savedTheme = localStorage.getItem('theme') || 'light';
        html.setAttribute('data-theme', savedTheme);
        updateThemeIcon(savedTheme);

        themeBtn.addEventListener('click', () => {
            const currentTheme = html.getAttribute('data-theme');
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme);
        });

        function updateThemeIcon(theme) {
            if (!themeIcon) return;
            themeIcon.setAttribute('href', theme === 'dark' ? '#i-sun' : '#i-moon');
            themeBtn.setAttribute('aria-label', theme === 'dark'
                ? 'Switch to the light theme'
                : 'Switch to the dark theme');
        }
    }

    const userMenuBtn = document.querySelector('.user-menu-btn');
    const userDropdown = document.querySelector('.user-dropdown');
    if (userMenuBtn && userDropdown) {
        userMenuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            userDropdown.classList.toggle('show');
        });

        document.addEventListener('click', () => {
            userDropdown.classList.remove('show');
        });
    }

    /* Category filtering toggles a class rather than writing inline display,
       so the grid keeps its own layout rules, and it surfaces a real empty
       state when a category has nothing in it. */
    const categoryItems = document.querySelectorAll('.category-item');
    const cards = document.querySelectorAll('.product-grid .hs-card');
    const categoryEmpty = document.getElementById('category-empty');

    categoryItems.forEach((item) => {
        item.addEventListener('click', () => {
            categoryItems.forEach((entry) => {
                entry.classList.remove('active');
                entry.setAttribute('aria-pressed', 'false');
            });
            item.classList.add('active');
            item.setAttribute('aria-pressed', 'true');

            const selectedCategory = item.getAttribute('data-category');
            let visible = 0;

            cards.forEach((card) => {
                const matches = selectedCategory === 'all'
                    || card.getAttribute('data-category') === selectedCategory;
                card.classList.toggle('is-filtered-out', !matches);
                if (matches) visible += 1;
            });

            if (categoryEmpty) {
                categoryEmpty.classList.toggle('hidden', visible > 0 || cards.length === 0);
            }
        });
    });

    initExpertChat();
});

/* =============================================================================
   SELF-MOVING ITEM RAILS

   A browsing row drifts sideways on its own so the catalogue reads as stock
   in motion rather than a static board. Written against the DOM directly —
   no carousel library, no jQuery, nothing added to the page weight.

   How it works: the track is duplicated once, so the row holds two identical
   copies of the listings. The engine advances scrollLeft by a few pixels a
   second and, the moment it passes the width of one copy, subtracts that
   width. The seam lands on identical content, so the wrap is invisible and
   there is no snap back to the start.

   Because it drives native scrollLeft rather than a transform, touch
   swiping, momentum, trackpads and the arrow keys all keep working for free.

   It stops whenever someone might be reading it: pointer over the row, a
   focused card inside it, a finger on the screen, a backgrounded tab, or the
   row scrolled out of view. Under prefers-reduced-motion it never starts.
   ========================================================================== */

function initItemRails() {
    const rails = document.querySelectorAll('[data-rail]');
    if (!rails.length) return;

    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    rails.forEach((rail) => {
        const track = rail.querySelector('[data-rail-track]');
        if (!track) return;

        const originals = Array.from(track.children);
        if (!originals.length) return;

        const speed = Number(rail.dataset.railSpeed) || 20;   // px per second
        let setWidth = 0;
        let cloned = false;
        let paused = false;
        let onScreen = true;
        let frame = null;
        let lastTime = 0;

        function measure() {
            // The width of one copy: everything up to the first clone.
            const gap = parseFloat(getComputedStyle(track).columnGap || '0') || 0;
            setWidth = originals.reduce((total, el) => total + el.offsetWidth + gap, 0);
        }

        function ensureClones() {
            if (cloned) return;
            measure();
            // Only loop a row that is actually wider than its frame. A short
            // row stays put and says so, rather than jittering in place.
            if (setWidth <= rail.clientWidth + 8) {
                rail.dataset.railStatic = 'true';
                return;
            }
            originals.forEach((el) => {
                const copy = el.cloneNode(true);
                copy.setAttribute('aria-hidden', 'true');
                // The duplicate is decoration; it must not be reachable by tab
                // or announced twice by a screen reader.
                copy.querySelectorAll('a, button, input, [tabindex]').forEach((node) => {
                    node.setAttribute('tabindex', '-1');
                });
                track.appendChild(copy);
            });
            cloned = true;
        }

        function step(now) {
            frame = requestAnimationFrame(step);
            if (!lastTime) { lastTime = now; return; }
            const delta = Math.min((now - lastTime) / 1000, 0.05);  // clamp after a stall
            lastTime = now;

            if (paused || !onScreen || document.hidden || !setWidth) return;

            rail.scrollLeft += speed * delta;
            if (rail.scrollLeft >= setWidth) {
                rail.scrollLeft -= setWidth;
            }
        }

        function start() {
            if (frame !== null || reduceMotion.matches) return;
            ensureClones();
            if (!cloned) return;
            lastTime = 0;
            frame = requestAnimationFrame(step);
        }

        function stop() {
            if (frame === null) return;
            cancelAnimationFrame(frame);
            frame = null;
        }

        const hold = () => { paused = true; };
        const release = () => { paused = false; lastTime = 0; };

        rail.addEventListener('pointerenter', hold);
        rail.addEventListener('pointerleave', release);
        rail.addEventListener('pointerdown', hold);
        rail.addEventListener('focusin', hold);
        rail.addEventListener('focusout', release);
        rail.addEventListener('touchstart', hold, { passive: true });
        rail.addEventListener('touchend', release, { passive: true });
        window.addEventListener('pointerup', release);

        // A wheel or a swipe can carry the row past the seam in either
        // direction, so the wrap is kept honest on both sides.
        rail.addEventListener('scroll', () => {
            if (!setWidth) return;
            if (rail.scrollLeft >= setWidth * 2) rail.scrollLeft -= setWidth;
            else if (rail.scrollLeft < 0) rail.scrollLeft += setWidth;
        }, { passive: true });

        if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach((entry) => { onScreen = entry.isIntersecting; });
            }, { rootMargin: '120px' });
            observer.observe(rail);
        }

        let resizeTimer = null;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimer);
            resizeTimer = setTimeout(() => {
                const previous = setWidth;
                measure();
                if (previous && setWidth) {
                    rail.scrollLeft = (rail.scrollLeft / previous) * setWidth;
                }
            }, 180);
        });

        // Respect a preference that changes while the page is open.
        const applyMotionPreference = () => {
            if (reduceMotion.matches) stop();
            else start();
        };
        if (reduceMotion.addEventListener) {
            reduceMotion.addEventListener('change', applyMotionPreference);
        }

        // Images decide the card width, so the first measurement waits for
        // the row to settle rather than guessing.
        if (document.readyState === 'complete') start();
        else window.addEventListener('load', start, { once: true });
    });
}

/* =============================================================================
   THE PHONE SHELL

   Two things the bottom tab bar needs from JavaScript, and nothing else: a
   real pixel height for the on-screen keyboard, and a hide-on-scroll rule
   for the chat screen where the composer and the bar compete for the same
   inch of glass.
   ========================================================================== */

function initPhoneShell() {
    const root = document.documentElement;

    /* The visual viewport shrinks when the keyboard opens. Publishing that
       overlap as a custom property lets the chat composer sit on top of the
       keyboard instead of underneath it, which no amount of CSS can work out
       on its own. */
    if (window.visualViewport) {
        const publishInset = () => {
            const overlap = Math.max(
                0,
                window.innerHeight - window.visualViewport.height - window.visualViewport.offsetTop
            );
            root.style.setProperty('--keyboard-inset', `${Math.round(overlap)}px`);
            root.classList.toggle('keyboard-open', overlap > 120);
        };
        window.visualViewport.addEventListener('resize', publishInset);
        window.visualViewport.addEventListener('scroll', publishInset);
        publishInset();
    }

    /* When the keyboard opens the conversation loses most of its height, and
       the message you were reading scrolls off the top. Hold the thread
       against its bottom edge — but only if it was already there, so this
       never yanks someone out of the history they scrolled back to. */
    const thread = document.getElementById('message-container');
    if (thread && window.visualViewport) {
        let wasAtBottom = true;
        const AT_BOTTOM = 48;

        thread.addEventListener(
            'scroll',
            () => {
                wasAtBottom =
                    thread.scrollHeight - thread.scrollTop - thread.clientHeight <
                    AT_BOTTOM;
            },
            { passive: true }
        );

        window.visualViewport.addEventListener('resize', () => {
            if (!wasAtBottom) return;
            requestAnimationFrame(() => {
                thread.scrollTop = thread.scrollHeight;
            });
        });
    }
}

/* =============================================================================
   PICTURES THAT DO NOT ARRIVE

   Listing photographs and member avatars are remote URLs, and remote URLs
   fail — a dead host, a blocked CDN, an image withdrawn since it was seeded.
   Left alone the browser shows a blank grey rectangle or a broken-image
   glyph, which reads as a broken page rather than as a listing with no
   photograph.

   The `error` event does not bubble, so this listens in the capture phase and
   hands the element over to the designed empty state the stylesheets already
   define. Avatars are redrawn as initials in the member's own card rather
   than fetched again from an avatar service.
   ========================================================================== */

const AVATAR_SELECTOR =
    '.chat-avatar-lg, .chat-avatar-md, .chat-avatar-sm, ' +
    '.profile-request-avatar, .profile-review-avatar, .profile-avatar-image, ' +
    '.user-pic-small, .ledger-thumb';

function initialsFrom(text) {
    const words = (text || '').trim().split(/\s+/).filter(Boolean);
    if (!words.length) return '?';
    if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
    return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

function handleBrokenImage(img) {
    if (img.dataset.fallbackApplied) return;
    img.dataset.fallbackApplied = '1';

    // A listing photograph: hand the card's wrapper its ruled empty state.
    const wrap = img.closest('.card-img-wrapper, .profile-item-image-wrap');
    if (wrap) {
        wrap.classList.add('is-missing');
        if (!wrap.dataset.fallback) {
            const card = wrap.closest('[data-category]');
            wrap.dataset.fallback =
                (card && card.dataset.category) || 'no photograph';
        }
        img.remove();
        return;
    }

    // A member avatar: draw the initials instead of asking a third party.
    if (img.matches(AVATAR_SELECTOR)) {
        const label =
            img.getAttribute('alt') ||
            img.closest('.chat-list-item, .chat-request-card, .profile-request-card, .chat-header-user')
                ?.querySelector('.chat-user-name, .chat-request-name, .profile-request-name, .chat-header-name')
                ?.textContent ||
            '';
        const mark = document.createElement('span');
        mark.className = img.className + ' avatar-initials';
        mark.setAttribute('aria-hidden', 'true');
        mark.textContent = initialsFrom(label);
        img.replaceWith(mark);
        return;
    }

    img.classList.add('img-failed');
}

function initBrokenImages() {
    document.addEventListener(
        'error',
        (event) => {
            const el = event.target;
            if (el instanceof HTMLImageElement) handleBrokenImage(el);
        },
        true
    );

    // Anything that already failed before this script ran.
    document.querySelectorAll('img').forEach((img) => {
        if (img.complete && img.naturalWidth === 0) handleBrokenImage(img);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initItemRails();
    initPhoneShell();
    initBrokenImages();
});
