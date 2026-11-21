# UI/UX fundamentals and engagement (motion, sound, haptics) for a hackathon weekend

Researched 2026-11-20. Repo names are `owner/repo` on GitHub. Verification note: the GitHub API
was blocked in the research sandbox, so star counts are omitted. Repos were confirmed through web
search or are long-standing, well-known projects. Before you depend on one, open it and check that
it is still maintained.

Legend: **[USEFUL]** worth your time this weekend · **[SITUATIONAL]** good, but only for some apps ·
**[HYPE]** looks great in a demo but costs time, bundle size or accessibility.

---

## Part 1: UI/UX fundamentals for building fast

### The principles that matter most (in priority order)

1. **Visual hierarchy: one primary action per screen.** Size, weight, color and position should
   all point to the single thing the user should do next. Use one filled primary button. Make the
   others secondary or ghost buttons. Squint at the screen: if nothing stands out, the hierarchy
   is broken. De-emphasize secondary text with a lighter gray rather than a smaller size.
2. **A fixed spacing scale.** Use only multiples of 4px (4, 8, 12, 16, 24, 32, 48, 64). Tailwind's
   default scale already does this, so don't use arbitrary values like `mt-[13px]`. Put more space
   *between* groups than *inside* them (proximity reads as relatedness). Too much whitespace looks
   intentional. Too little looks broken.
3. **Typography: one font family and about 5 sizes.** For example 12/14/16/20/30px. Body text at
   least 16px, line height about 1.5, line length 45–75 characters (`max-w-prose`). Show
   hierarchy with weight (400/500/600) before reaching for more sizes. A system font stack or
   Inter/Geist is enough.
4. **Color and contrast: neutrals plus one accent, and pass WCAG AA.** Text needs a 4.5:1
   contrast ratio, large text and UI component outlines need 3:1. Never use color as the only
   signal (add an icon or text to error states). Make the gray palette slightly warm or cool, not
   pure #888. Treat dark mode as a nice-to-have: shadcn/Radix give it to you almost free.
5. **Every async view has 4 states: loading, empty, error, success.** This is the most common
   hackathon miss. Loading: a skeleton that matches the final layout, not a spinner in the middle
   of a blank page. Empty: explain what goes here plus a call to action ("No projects yet,
   Create one"). Error: say what happened, in plain words, with a retry button. Also cover the
   disabled, hover, focus-visible, and pressed states on every interactive element.
6. **Consistency beats originality.** Reuse one component per job (one Button, one Card, one
   Dialog). Use the same radius, shadow and icon set (Lucide) everywhere. Follow platform
   conventions (Jakob's Law: users expect your app to work like the apps they already use).
7. **Fitts's and Hick's laws.** Fitts: bigger and closer targets are faster to hit. Touch targets
   should be at least 44×44pt (Apple HIG) / 48dp (Material), and primary actions belong in thumb
   reach on mobile. Hick: more choices means slower decisions, so trim menus, use sensible
   defaults, and hide advanced options behind progressive disclosure.
8. **Mobile-first, then perceived performance.** Design at 375px wide first, then add `md:` and
   `lg:` breakpoints. For perceived speed: optimistic UI (update immediately, roll back on
   failure), skeletons, under 100ms feedback on every press, prefetching on hover, and no layout
   shift (reserve space for images). Any action over about 1s needs a progress indicator.

Source for principles 6–8: [Laws of UX](https://lawsofux.com). Vercel's
[Web Interface Guidelines](https://vercel.com/design/guidelines) are the best concrete checklist
for states, focus, forms, and perceived performance.

### Best resources and libraries

| Repo | What it is | When to pick it |
|---|---|---|
| `shadcn-ui/ui` | Copy-paste React components (Radix + Tailwind) that you own in your codebase. Has a CLI, blocks, charts, and themes. | **[USEFUL] Default pick for a React/Next app.** Accessible, looks professional out of the box, easy to edit. |
| `radix-ui/primitives` | Unstyled, accessible primitives (Dialog, Popover, Select…) | **[USEFUL]** when you want full control over styling. shadcn is built on it. |
| `tailwindlabs/tailwindcss` | Utility CSS with a built-in spacing, type and color scale | **[USEFUL]** The scale enforces consistency for you. Tailwind UI / Tailwind Plus (paid) is good for full page patterns. |
| `mantinedev/mantine` | Full React component library with 100+ components and hooks | **[USEFUL]** if you need data-heavy UI (date pickers, forms, notifications) with no styling work. |
| `adobe/react-spectrum` (React Aria) | The strongest accessibility behavior hooks available | **[SITUATIONAL]** when accessibility is a judging criterion. |
| `saadeghi/daisyui` | Tailwind plugin that gives semantic class names (`btn btn-primary`) | **[USEFUL]** for non-React stacks or plain HTML pages. |
| `material-components/material-web` | Google's Material 3 web components | **[SITUATIONAL]** if the app should look like an Android/Google app. |
| `lucide-icons/lucide` | Consistent open-source icon set | **[USEFUL]** Pick one icon set and stick with it. |
| `pacocoursey/cmdk` | ⌘K command menu | **[SITUATIONAL]** cheap way to look like a power-user product. |
| `emilkowalski/sonner` | Toast notifications | **[USEFUL]** Success and error feedback in one line of code. |
| `emilkowalski/vaul` | Mobile drawer / bottom sheet | **[USEFUL]** for mobile-first layouts. |
| `magicuidesign/magicui`, Aceternity UI | Animated "landing page" components | **[HYPE]** Fine for one hero section. They hurt readability and performance if you use them everywhere. |

Curated lists and checklists:
- `alexpate/awesome-design-systems`: a directory of public design systems (Polaris, Primer,
  Carbon…). Use it to copy patterns from a mature system.
- `vercel-labs/web-interface-guidelines`: an actionable rule list. It ships a `command.md` file
  that coding agents can use to review your UI. **[USEFUL]** Run it against your app before demo.
- `raunofreiberg/interfaces`: Rauno Freiberg's list of small interaction details that make an
  interface feel polished.
- `thedaviddias/Front-End-Checklist`: a pre-launch checklist (meta tags, performance,
  accessibility).
- `bradtraversy/design-resources-for-developers`: fonts, colors, illustrations, and stock assets.
- `gztchan/awesome-design`: a broad design-tools list. Use it for browsing, not for learning.
- Apple HIG: https://developer.apple.com/design/human-interface-guidelines (touch targets, motion,
  sound, haptics). Material 3: https://m3.material.io (motion tokens, states). Book: *Refactoring
  UI* (Wathan & Schoger), the best single resource on visual design for developers.
- Contrast checker: https://webaim.org/resources/contrastchecker/ · accessibility checklist:
  https://www.a11yproject.com/checklist/

### Ship-it-in-a-weekend checklist (UI)
- [ ] `npx shadcn@latest init`, choose one base color and one radius, and don't change them again.
- [ ] Write down the type scale (5 sizes) and spacing scale (Tailwind defaults). No arbitrary values.
- [ ] Each screen has exactly one primary button.
- [ ] Each data view has a skeleton, an empty state with a call to action, and an error state with retry.
- [ ] Every interactive element has hover, focus-visible, active, and disabled styles.
- [ ] Check contrast for body text, muted text, and placeholder text (AA).
- [ ] Test at 375px: touch targets ≥44px, no horizontal scroll, primary action in thumb reach.
- [ ] Optimistic updates plus a toast for create, update, and delete actions.
- [ ] Use only one icon set, one font, and one shadow style.
- [ ] Run the Vercel Web Interface Guidelines check before the demo, and tab through the whole flow with the keyboard.

---

## Part 2: What makes an app feel engaging

### The principles that matter most

1. **Motion must have a purpose.** Use it to show cause and effect (this button made that
   happen), spatial continuity (where an element came from or went), or state change. Decorative
   motion that repeats on every visit becomes noise. Rule of thumb: animate high-frequency actions
   lightly or not at all, and save the big moments (confetti, celebration) for rare events like
   finishing a task or reaching a milestone.
2. **Keep durations short.** NN/g puts most UI animation in the 100–500ms range: about 100ms for
   simple feedback (toggles, checkboxes), 200–300ms for modals and screen changes, and around
   400ms only for large movements. Animations are far more often too slow than too fast, and
   "at 500ms they start to feel like a real drag". Exits should be slightly faster than entries.
   ([NN/g: Animation duration](https://www.nngroup.com/articles/animation-duration/))
3. **Easing.** Use `ease-out` for entering and responding to the user (fast start, so it feels
   responsive), `ease-in` only for elements leaving, and `ease-in-out` for moving elements on
   screen. Avoid `linear` except for spinners and progress bars. Springs (motion or react-spring)
   feel more natural for drag gestures and can be interrupted midway.
4. **Respect `prefers-reduced-motion`.** Replace large movement, parallax, and zoom with a fade
   or nothing at all. Don't disable feedback completely. In Motion use `useReducedMotion()` or
   `<MotionConfig reducedMotion="user">`. In CSS use
   `@media (prefers-reduced-motion: reduce)`. This is also a WCAG requirement (2.3.3).
5. **Sound is off by default, short, and quiet.** Browsers block autoplay until the user
   interacts with the page anyway. Provide a visible mute toggle and remember the choice in
   localStorage. Keep sounds under 300ms, at low volume, and pitch-vary repeated sounds (±5–10%)
   so they don't feel mechanical. Never use sound as the only signal. Sound fits games, playful
   and creative apps, and celebrations. It does not fit productivity or B2B tools.
6. **Haptics: one subtle pulse on meaningful commits only** (success, toggle, snapping into
   place). Android supports `navigator.vibrate()`. **iOS Safari has never shipped the Vibration
   API**, so libraries work around it with a hidden `<input type="checkbox" switch>`, which
   triggers a single Taptic pulse (iOS 17.4+). Treat haptics as a progressive enhancement.
7. **Microinteractions = trigger → feedback → state.** Press scale (`active:scale-95`, about
   100ms), a checkmark that draws in, a count-up number, an item sliding into a list,
   copy→"Copied!". These cheap touches give the most perceived polish per hour of work.
8. **Game feel / "juice" (only where it fits).** Juice means a layered, slightly exaggerated
   response to an action. Techniques: screen shake (small, short, decaying), squash and stretch,
   particles and confetti, hit-stop (freeze for 30–80ms on impact), tweened scale "pop" on
   score changes, a flash when something is hit, sound plus motion together. Use it lightly in a
   web app: a single confetti burst on a milestone, not on every click.

### Key talks and references (game feel)
- **"Juice it or lose it"**: Martin Jonasson and Petri Purho, Nordic Game Jam 2012. They add
  juice step by step to a plain Breakout prototype, live. Video: https://www.youtube.com/watch?v=Fy0aCDmgnxg.
  The demo source is the "juicy-breakout" project by grapefrukt (mirrored at
  https://sourceforge.net/projects/juicy-breakout.mirror/).
- **"The art of screenshake"**: Jan Willem Nijman (Vlambeer), about 30 tricks for game feel.
  https://www.youtube.com/watch?v=AJdEqssNZ-U
- `deepnight/gamefeel`: an open-source prototype that goes with Sébastien Bénard's 2019 game-feel
  talk. Each juice technique can be toggled on and off.
- `omiyagames/make-it-juicy`: a Unity sample project based on "Juice it or lose it".
- *Game Feel* (Steve Swink, 2008), the book that gave the topic its name. Also Kenney's list of
  must-see videos for indie developers: https://kenney.nl/learn/must-see-videos-for-indie-developers.
  There is no well-maintained "awesome-game-feel" list. Use `FronkonGames/Awesome-Gamedev` instead.

### Best libraries

**Motion**
| Repo | For | When to pick | Verdict |
|---|---|---|---|
| `motiondivision/motion` (Motion, formerly Framer Motion, `npm i motion`, import from `motion/react`) | Declarative React/JS/Vue animation: layout animations, exit animations via `AnimatePresence`, gestures, springs | Default for React apps | **[USEFUL]** It became independent of Framer in Nov 2024 and is MIT licensed. Old `framer-motion` imports still work. |
| `formkit/auto-animate` | One line (`useAutoAnimate()`) animates list add, remove, and reorder | Lists, todo items, filters; any framework | **[USEFUL]** Best polish per minute of effort. |
| `greensock/GSAP` | Timeline animation engine, ScrollTrigger, SVG morphing | Scroll-driven stories, complex sequenced hero animations, non-React stacks | **[USEFUL]** All plugins have been free since the 2025 Webflow acquisition. It is overkill for buttons and modals. |
| `pmndrs/react-spring` | Physics-based springs | Drag and gesture-heavy UI, or alongside react-three-fiber | **[SITUATIONAL]** Motion covers most of the same use cases. |
| `airbnb/lottie-web` / `LottieFiles/dotlottie-web` | Play After Effects animations exported as JSON or .lottie files | A designer-quality empty-state, success, or onboarding illustration from LottieFiles | **[SITUATIONAL]** lottie-web is large (about 250KB) and maintained less actively. Prefer dotlottie-web. |
| `rive-app/rive-wasm` | Interactive state-machine animations (Rive) | Animated characters or mascots that react to input | **[SITUATIONAL]** It has a learning curve, so it's only worth it if someone on the team already knows Rive. |
| View Transitions API (native browser feature) | `document.startViewTransition()` crossfades or morphs between DOM states and route changes | Page and route transitions with no library | **[USEFUL]** Same-document transitions are Baseline as of Oct 2025 (Firefox 144). Cross-document (multi-page app) support is still partial, so check https://caniuse.com/cross-document-view-transitions. |
| `catdad/canvas-confetti` | Confetti in one call | Celebration moments | **[USEFUL]** About 6KB. Pass `disableForReducedMotion: true`. |
| `tsparticles/tsparticles` | Particle backgrounds and effects | Particle effects in a game | **[HYPE]** for app backgrounds: heavy on CPU and adds nothing to the product. |
| `ibelick/motion-primitives`, Magic UI | Pre-built Motion and shadcn animated components | Grabbing a polished text or number effect | **[SITUATIONAL]** Copy one or two components, not the whole kit. |

**Sound**
| Repo | For | When to pick | Verdict |
|---|---|---|---|
| `goldfire/howler.js` | Cross-browser audio playback: sprites, volume, mobile unlock | Any web app or game playing short sound effects | **[USEFUL]** The standard choice, with no dependencies. |
| `joshwcomeau/use-sound` | React hook around howler (`const [play] = useSound(url)`) | React apps | **[USEFUL]** Supports sprites, `playbackRate` for pitch variation, and an `interrupt` option. Article: https://www.joshwcomeau.com/react/announcing-use-sound-react-hook/ |
| `Tonejs/Tone.js` | Web Audio synthesis, scheduling, and music | Generating sounds procedurally, or music and rhythm apps | **[SITUATIONAL]** Overkill for playing a click sound. |
| Asset sources | Kenney.nl audio packs (CC0), https://freesound.org, https://sfxr.me (jsfxr, retro sound-effect generator) | Getting sounds in minutes | **[USEFUL]** Check licenses. Kenney is CC0. |

**Haptics**
| Repo | For | Verdict |
|---|---|---|
| `lochie/web-haptics` | Presets (success, nudge, error, buzz). Uses `navigator.vibrate` on Android and the iOS switch-checkbox trick on iOS 17.4+. Silently does nothing on unsupported platforms. | **[USEFUL]** but a young project. iOS gives one kind of pulse only, with no intensity control. |
| `mkuczera/react-native-haptic-feedback` / Expo Haptics | Native haptics in React Native or Expo | **[USEFUL]** if the app is native. Real haptics only work well there. |
| Packages claiming "navigator.vibrate on iOS 18" (e.g. `ios-vibrator-pro-max`) | — | **[HYPE]** Unofficial and depends on iOS version. Apple tightened the behavior in iOS 18.4. |

### Hype vs. genuinely useful (be honest with yourself)
- **Genuinely useful:** press feedback, list auto-animate, toasts, skeletons, one well-timed
  success animation, optimistic UI, route crossfades. These make the app *feel fast*, and judges
  notice that.
- **Hype:** scroll-jacking, parallax everywhere, animated gradient blobs, typewriter text
  effects on every heading, particle backgrounds, 3D tilt cards, sounds on every click. They cost
  time, frame rate, and accessibility, and they look generic in 2026 because AI-generated
  landing pages all use them.
- Animate only `transform` and `opacity` (they run on the GPU). Animating `width`, `height`, or
  `top` causes jank on demo laptops and phones.

### Ship-it-in-a-weekend checklist (engagement)
- [ ] `npm i motion`. Wrap the app in `<MotionConfig reducedMotion="user">`.
- [ ] Add `transition-[transform,opacity] duration-150 ease-out active:scale-95` to buttons and cards.
- [ ] Use `useAutoAnimate()` on every list that changes.
- [ ] Use `AnimatePresence` for modals, drawers, and toasts (200–250ms in, about 150ms out).
- [ ] One "hero moment" for the core success event: confetti, a Lottie checkmark, or a count-up
      number, with an optional sound and haptic pulse.
- [ ] Sound (if it fits the app): `use-sound`/howler, off by default or behind a visible mute
      toggle saved in localStorage, at 0.3–0.5 volume, with ±8% `playbackRate` jitter.
- [ ] Haptics: `web-haptics` `success` on that same moment, on mobile only.
- [ ] Use the View Transitions API (or Next.js `<ViewTransition>`) for route changes if supported, falling back to no animation.
- [ ] Test with "Reduce motion" turned on in the OS settings and with the sound muted. The app must still be fully usable.
- [ ] Throttle the CPU 4× in DevTools and check that animations still hold 60fps. If one doesn't, cut it.

---

## Sources
- NN/g, Executing UX Animations, Duration: https://www.nngroup.com/articles/animation-duration/
- Laws of UX (Jon Yablonski): https://lawsofux.com
- Vercel Web Interface Guidelines: https://vercel.com/design/guidelines · https://github.com/vercel-labs/web-interface-guidelines
- Rauno Freiberg, interfaces: https://github.com/raunofreiberg/interfaces
- Awesome design systems: https://github.com/alexpate/awesome-design-systems
- Motion becomes independent: https://motion.dev/blog/framer-motion-is-now-independent-introducing-motion · https://github.com/motiondivision/motion
- Same-document View Transitions are Baseline: https://web.dev/blog/same-document-view-transitions-are-now-baseline-newly-available
- View transitions 2025 update: https://developer.chrome.com/blog/view-transitions-in-2025
- Interop 2026 (cross-document view transitions): https://hacks.mozilla.org/2026/02/launching-interop-2026/
- Cross-document view transitions support: https://caniuse.com/cross-document-view-transitions
- Vibration API implementation report (no WebKit support): https://w3c.github.io/vibration/reports/implementation.html
- web-haptics: https://github.com/lochie/web-haptics · browser support: https://www.mintlify.com/lochie/web-haptics/advanced/browser-support
- Juice it or lose it (talk): https://www.youtube.com/watch?v=Fy0aCDmgnxg · juicy-breakout mirror: https://sourceforge.net/projects/juicy-breakout.mirror/
- The art of screenshake: https://www.youtube.com/watch?v=AJdEqssNZ-U
- deepnight/gamefeel: https://github.com/deepnight/gamefeel · omiyagames/make-it-juicy: https://github.com/omiyagames/make-it-juicy
- Kenney, must-see videos for indie developers: https://kenney.nl/learn/must-see-videos-for-indie-developers
- Game feel (overview): https://en.wikipedia.org/wiki/Game_feel
- Apple HIG: https://developer.apple.com/design/human-interface-guidelines · Material 3: https://m3.material.io
- WebAIM contrast checker: https://webaim.org/resources/contrastchecker/
