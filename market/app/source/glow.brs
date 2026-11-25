' What the reef gives off at night. Corals fluoresce under a tank's blue light: here and there
' the tips of their branches, the rim of a plate, the grooves of a brain coral. Each reef
' structure has that light as pictures of its own (reef_<name>_glow_a.png and _b.png, at half
' size), split between two so that one part of the reef can brighten while the other dims.
' They are drawn over the night's dark, so they shine out of it, and before everything that
' stands or swims in front of the reef (PanFrame), so they never show through it. By day
' they are not drawn at all.
'
' Scene config:
'   cfg.glow       [{ a, b: picture paths, x, y: where the structure stands }, ...]
'   cfg.floorGlow  { img, x, y, k }: the light the glow throws on the sand, a picture of the
'                  whole floor 1/k of its size

sub GlowInit(s as object)
    s.reefGlow = []
    if s.cfg.glow = invalid then return
    for each g in s.cfg.glow
        e = { x: g.x, y: g.y, parts: [] }
        for each path in [g.a, g.b]
            tx = LoadTexture(path)
            if tx <> invalid
                r = CreateObject("roRegion", tx.bmp, 0, 0, tx.bmp.GetWidth(), tx.bmp.GetHeight())
                r.SetScaleMode(1)
                e.parts.Push({ r: r, kx: tx.kx * 2, ky: tx.ky * 2 })
                e.w = tx.w * 2
            end if
        end for
        if e.parts.Count() > 0 then s.reefGlow.Push(e)
    end for
    ' The light that glow throws on the sand: one soft picture for the whole floor, kept small.
    s.floorGlow = invalid
    fg = s.cfg.floorGlow
    if fg <> invalid
        tx = LoadTexture(fg.img)
        if tx <> invalid
            r = CreateObject("roRegion", tx.bmp, 0, 0, tx.bmp.GetWidth(), tx.bmp.GetHeight())
            r.SetScaleMode(1)
            s.floorGlow = { r: r, x: fg.x, y: fg.y, kx: tx.kx * fg.k, ky: tx.ky * fg.k, w: tx.w * fg.k }
        end if
    end if
    LogMemory("glow")
end sub

' The reef's glow at its strongest (0 .. 255). It is an accent: well short of full, so that
' the night stays dark and the tree's lights stay the brightest things in it.
function GLOW_ALPHA() as integer
    return 150
end function

' How strongly things glow now: nothing by day, rising through dusk, full in Night Lite.
function GlowLevel(s as object) as float
    if s.nightLite then return 1.0
    return s.night
end function

sub ReefGlow(s as object, screen as object, t as float)
    level = GlowLevel(s)
    if level < 0.04 then return
    fg = s.floorGlow
    if fg <> invalid
        sx = fg.x - s.camX
        if sx < 1920 and sx + fg.w > 0 then screen.DrawScaledObject(sx, fg.y, fg.kx, fg.ky, fg.r, &hFFFFFF00 + Int(120 * level * (0.85 + 0.15 * Sin(t * 0.4))))
    end if
    n = 0
    for each e in s.reefGlow
        sx = e.x - s.camX
        if sx < 1920 and sx + e.w > 0
            k = 0
            for each part in e.parts
                ' The two parts breathe against each other, each structure a little out of step.
                wave = 0.65 + 0.35 * Sin(t * 0.55 + 3.14159 * k + 1.3 * n)
                screen.DrawScaledObject(sx, e.y, part.kx, part.ky, part.r, &hFFFFFF00 + Int(GLOW_ALPHA() * level * wave))
                k = k + 1
            end for
        end if
        n = n + 1
    end for
end sub
