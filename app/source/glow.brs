' What the reef gives off at night. Corals fluoresce under a tank's blue light: their growing
' tips, their polyps' mouths, the grooves of a brain coral. Each reef structure has that light
' as pictures of its own (reef_<name>_glow_a.png and _b.png, at half size), split between two
' so that one part of the reef can brighten while the other dims. They are drawn over the
' night's dark, so they shine out of it; by day they are not drawn at all.
'
' Scene config (cfg.glow): [{ a, b: picture paths, x, y: where the structure stands }, ...]

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
    LogMemory("glow")
end sub

' How strongly things glow now: nothing by day, rising through dusk, full in Night Lite.
function GlowLevel(s as object) as float
    if s.nightLite then return 1.0
    return s.night
end function

sub ReefGlow(s as object, screen as object, t as float)
    level = GlowLevel(s)
    if level < 0.04 then return
    n = 0
    for each e in s.reefGlow
        sx = e.x - s.camX
        if sx < 1920 and sx + e.w > 0
            k = 0
            for each part in e.parts
                ' The two parts breathe against each other, each structure a little out of step.
                wave = 0.7 + 0.3 * Sin(t * 0.55 + 3.14159 * k + 1.3 * n)
                screen.DrawScaledObject(sx, e.y, part.kx, part.ky, part.r, &hFFFFFF00 + Int(235 * level * wave))
                k = k + 1
            end for
        end if
        n = n + 1
    end for
end sub
