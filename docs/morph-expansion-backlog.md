# Morph Expansion Backlog

This document tracks morph ideas that are deferred or partially deferred after the PIL-first expansion.

## Status

- Implemented now: broad static PNG morph catalog using PIL primitives and layered recipes.
- Deferred: effects that are animation-first, shader-like, or too expensive/noisy for current runtime constraints.

## Deferred Buckets

### Animation-First Effects (defer until GIF/APNG/video path)

- Shimmer sweep
- Pulsing glow
- Cycling rainbow tint
- Flickering lightning
- TV glitch flicker
- Floating particles
- Heat-haze movement
- Rising smoke bands
- Falling snow loop
- Dripping slime animation
- Rune flicker
- VHS jitter loop

### High-Cost Distortion Effects (defer pending performance budget)

- Spiral twist variants
- Dense ripple warp families
- Complex lens refraction chains
- Heavy multi-pass blur plus displacement stacks
- Deep kaleidoscope/tunnel repeat variants

### Shader-Like / Non-PIL-Exact Effects (defer until alternate renderer)

- Physically accurate refraction and caustics
- True metallic BRDF-like foil response
- Real-time dynamic specular sheens tied to camera angle
- High-fidelity chromatic aberration with depth cues

## PNG-to-GIF Migration Notes

If the project moves from static PNG attachments to GIF/APNG animation, treat it as an explicit architecture phase.

### Pipeline Implications

- Render pipeline must support frame sequences (`N` frames per morph) instead of single-frame output.
- Morph definitions should support static and animated variants:
  - static: one rendered image
  - animated: frame generator with deterministic seed and timing metadata
- Add per-morph frame-budget limits to avoid runaway CPU usage.

### Runtime and Caching

- Introduce cache keys that include frame count, timing profile, and seed.
- Consider precomputing popular animated variants or using short-lived caches to control hot-path latency.
- Keep static fallback for environments where animation generation fails or is disabled.

### Discord Delivery Constraints

- Animated files are larger; enforce size and frame caps.
- Add adaptive quality strategy (resolution/frame count/quantization) to stay within upload limits.
- Keep command UX responsive by deferring heavy rendering or using interim status embeds for long renders.

### UX and Economy Considerations

- Decide whether animated morphs are separate high-tier outcomes or a style layer on top of static morphs.
- If animation is premium-only, align rarity and value multiplier policy accordingly.
- Ensure confirmation flows still show clear before/after previews even for animated outputs.

## Next Steps

1. Keep expanding static PIL-safe recipes first while tracking render latency in development.
2. Prototype a small animated morph spike in a separate branch before any production rollout.
3. Define objective guardrails for animation adoption (latency, size, and failure-mode behavior).
