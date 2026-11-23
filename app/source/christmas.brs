' Christmas in the reef: a fire in the hearth, bubbles from the chimney, strings of lights on
' the corals and on the tree, and the glow of the tree's star. The tree, fireplace and gifts
' themselves are ordinary reef pieces (scenes/tank.json); this file animates what moves. Everything here is optional and loads after the reef and the
' fish: whatever does not fit in graphics memory is simply left out.
'
' Scene config (cfg.christmas, tank coordinates):
'   fire      { x, y, w, h, frames, cols }   where the flame sheet's cells are drawn
'   hearth    [x, y]                         centre of the firelight
'   chimney   [x, y]                         mouth of the chimney pot
'   surface   y where a bubble reaches the top
'   tiles     [[x, y, atlasX, atlasY, w, h], ...]   wire and bulbs, cut from xmas_lights.png
'   bulbs     [[x, y, colour], ...]          the reefs' sorted by x; the tree's follow, in the
'                                            order they hang on its string, as [x, y, colour, group]
'   star      [x, y]                         centre of the tree's topper

' A cell of a sheet loaded with LoadTexture: the region, where its pixels really start (dx, dy:
' on a 720p Roku the shrunk sheet's edges are rounded) and the scale that restores its size.
function XmasCell(tx as object, x as integer, y as integer, w as integer, h as integer) as object
    if tx.kx = 1 and tx.ky = 1
        return { r: CreateObject("roRegion", tx.bmp, x, y, w, h), dx: 0, dy: 0, kx: 1.0, ky: 1.0, w: w, h: h }
    end if
    x0 = Int(x / tx.kx + 0.5) : x1 = Int((x + w) / tx.kx + 0.5)
    y0 = Int(y / tx.ky + 0.5) : y1 = Int((y + h) / tx.ky + 0.5)
    r = TextureRegion(tx, x0, y0, x1 - x0, y1 - y0)
    return { r: r, dx: x0 * tx.kx - x, dy: y0 * tx.ky - y, kx: tx.kx, ky: tx.ky, w: w, h: h }
end function

sub XmasDrawCell(screen as object, cell as object, x as float, y as float, alpha as integer)
    if alpha <= 0 then return
    if alpha > 255 then alpha = 255
    if cell.kx = 1 and cell.ky = 1
        screen.DrawObject(Int(x + 0.5), Int(y + 0.5), cell.r, &hFFFFFF00 + alpha)
    else
        screen.DrawScaledObject(x + cell.dx, y + cell.dy, cell.kx, cell.ky, cell.r, &hFFFFFF00 + alpha)
    end if
end sub

sub ChristmasInit(s as object)
    s.xmas = invalid
    c = s.cfg.christmas
    if c = invalid then return
    x = { fire: invalid, glows: invalid, star: invalid, bubbles: [], bubbleCells: invalid, tiles: [], bulbs: [], level: [0, 0, 0, 0, 0, 0, 0, 0] }
    x.puff = 2.0 : x.trickle = 0.5 : x.burst = 0
    ' Small sprites first: they cost little and carry most of the life.
    gb = LoadBitmap("pkg:/images/xmas_glows.png")
    if gb <> invalid
        x.glows = []
        for i = 0 to 5
            r = CreateObject("roRegion", gb, i * 64, 0, 64, 64)
            r.SetScaleMode(1)
            x.glows.Push(r)
        end for
    end if
    if c.star <> invalid then x.star = LoadBitmap("pkg:/images/star_glow.png")
    bb = LoadBitmap("pkg:/images/xmas_bubbles.png")
    if bb <> invalid and c.chimney <> invalid
        x.bubbleCells = []
        for i = 0 to 1
            r = CreateObject("roRegion", bb, i * 40, 0, 40, 40)
            r.SetScaleMode(1)
            x.bubbleCells.Push(r)
        end for
        for i = 1 to 18
            x.bubbles.Push({ live: false, x: 0.0, y: 0.0, x0: 0.0, sc: 0.5, vy: 0.0, ph: 0.0, sw: 0.0, age: 0.0, cell: 0 })
        end for
    end if
    if c.fire <> invalid
        fb = LoadBitmap("pkg:/images/xmas_fire.png")
        if fb <> invalid
            x.fire = []
            for i = 0 to c.fire.frames - 1
                x.fire.Push(CreateObject("roRegion", fb, (i mod c.fire.cols) * c.fire.w, Int(i / c.fire.cols) * c.fire.h, c.fire.w, c.fire.h))
            end for
        end if
    end if
    if c.tiles <> invalid
        tx = LoadTexture("pkg:/images/xmas_lights.png")
        if tx <> invalid
            for each tl in c.tiles
                x.tiles.Push({ x: tl[0], y: tl[1], w: tl[4], cell: XmasCell(tx, tl[2], tl[3], tl[4], tl[5]) })
            end for
        end if
    end if
    ' A glow needs a bulb under it: the reefs' bulbs are on that sheet of wire, the tree's are
    ' part of the tree. A bulb's group sets its place in the twinkle and the chase.
    if c.bulbs <> invalid and x.glows <> invalid
        k = 0
        for each b in c.bulbs
            if b.Count() > 3
                x.bulbs.Push({ x: b[0], y: b[1], c: b[2], g: b[3] })
            else if x.tiles.Count() > 0
                x.bulbs.Push({ x: b[0], y: b[1], c: b[2], g: k mod 8 })
            end if
            k = k + 1
        end for
    end if
    s.xmas = x
    LogMemory("christmas")
end sub

sub ChristmasUpdate(s as object, t as float, dt as float)
    x = s.xmas
    if x = invalid then return
    c = s.cfg.christmas

    ' Eight shared brightness levels keep the animation independent of the bulb count.
    ' Night Lite uses a slower twinkle. The regular show blends twinkle with a chase.
    if s.nightLite
        for g = 0 to 7
            x.level[g] = 0.62 + 0.38 * Sin(t * (0.55 + 0.17 * g) + g * 2.4)
        end for
        return
    end if
    show = 0.5 + 0.5 * Sin(t * 0.085)
    show = show * show * (3 - 2 * show)
    for g = 0 to 7
        twinkle = 0.62 + 0.38 * Sin(t * (1.1 + 0.37 * g) + g * 2.4)
        chase = 0.5 + 0.5 * Sin(t * 3.3 - g * 0.785)
        chase = 0.18 + 0.82 * chase * chase
        x.level[g] = twinkle + (chase - twinkle) * show
    end for

    ' Chimney: a steady trickle of bubbles, and every few seconds a puff of several.
    if x.bubbleCells = invalid then return
    x.trickle = x.trickle - dt
    x.puff = x.puff - dt
    if x.puff <= 0
        x.burst = 4 + Int(Rnd(0) * 4)
        x.puff = RndRange(5, 9)
    end if
    if x.trickle <= 0
        ChristmasBubble(x, c)
        x.trickle = RndRange(0.45, 0.95)
        if x.burst > 0
            x.burst = x.burst - 1
            x.trickle = RndRange(0.06, 0.16)
        end if
    end if
    top = 60
    if c.surface <> invalid then top = c.surface
    for each b in x.bubbles
        if b.live
            b.age = b.age + dt
            ' Bubbles speed up and wobble wider as they rise.
            b.vy = b.vy + 14 * dt
            b.y = b.y - b.vy * dt
            b.x = b.x0 + (4 + 9 * b.sw * b.age) * Sin(b.age * (2.2 + b.sw) + b.ph)
            if b.y < top then b.live = false
        end if
    end for
end sub

sub ChristmasBubble(x as object, c as object)
    for each b in x.bubbles
        if not b.live
            b.live = true
            b.age = 0
            b.x0 = c.chimney[0] + RndRange(-7, 7)
            b.x = b.x0
            b.y = c.chimney[1] + 4
            b.sc = RndRange(0.22, 0.62)
            b.vy = 38 + 50 * b.sc
            b.ph = Rnd(0) * 6.28
            b.sw = Rnd(0)
            b.cell = Int(Rnd(0) * 2)
            return
        end if
    end for
end sub

' The wire and bulbs strung on the reefs' corals. Drawn before the pieces that stand in front
' of the reefs, so a string runs behind the tree.
sub ChristmasWires(s as object, screen as object)
    x = s.xmas
    if x = invalid then return
    cam = s.camX
    for each tl in x.tiles
        sx = tl.x - cam
        if sx < 1920 and sx + tl.w > 0 then XmasDrawCell(screen, tl.cell, sx, tl.y, 255)
    end for
end sub

' Drawn over the reef pieces and behind the fish that swim in front of them.
sub ChristmasDraw(s as object, screen as object, t as float)
    x = s.xmas
    if x = invalid then return
    c = s.cfg.christmas
    cam = s.camX
    ChristmasFire(s, screen, t, 255)
    ChristmasGlows(s, screen, 1.0)
    ChristmasStar(s, screen, t, 1.0)
    if x.bubbleCells <> invalid
        top = 60
        if c.surface <> invalid then top = c.surface
        for each b in x.bubbles
            if b.live
                sx = b.x - cam
                if sx > -40 and sx < 1960
                    ' Fade in at the pot and out just under the surface.
                    a = 235
                    if b.age < 0.25 then a = Int(235 * b.age / 0.25)
                    if b.y < top + 50 then a = Int(a * (b.y - top) / 50)
                    k = b.sc * (1 + 0.12 * b.age)
                    if a > 0 then screen.DrawScaledObject(sx - 20 * k, b.y - 20 * k, k, k, x.bubbleCells[b.cell], &hFFFFFF00 + a)
                end if
            end if
        end for
    end if
end sub

' Drawn after the night tint, so the fire and the bulbs shine in a dark tank.
sub ChristmasNight(s as object, screen as object, t as float)
    if s.xmas = invalid or s.night < 0.04 then return
    if s.nightLite
        ChristmasGlows(s, screen, 0.5)
        ChristmasStar(s, screen, t * 0.5, 0.36)
        return
    end if
    ChristmasFire(s, screen, t, Int(255 * s.night))
    ChristmasGlows(s, screen, 0.35 + 0.65 * s.night)
    ChristmasStar(s, screen, t, 0.35 + 0.65 * s.night)
end sub

' The topper's glow: a slow uneven pulse with a bright glint at its peak.
sub ChristmasStar(s as object, screen as object, t as float, gain as float)
    x = s.xmas
    c = s.cfg.christmas
    if x.star = invalid then return
    sx = c.star[0] - s.camX
    if sx < -110 or sx > 2030 then return
    beat = 0.5 + 0.5 * Sin(t * 2.6 + 0.8 * Sin(t * 0.74))
    glint = beat * beat * beat * beat
    k = 1.2 + 0.4 * glint
    a = Int((96 + 150 * glint) * gain)
    screen.DrawScaledObject(sx - 64.5 * k, c.star[1] - 64.5 * k, k, k, x.star, &hFFFFFF00 + a)
end sub

sub ChristmasFire(s as object, screen as object, t as float, alpha as integer)
    x = s.xmas
    c = s.cfg.christmas
    if c.fire = invalid then return
    sx = c.fire.x - s.camX
    if sx > 2100 or sx + c.fire.w < -180 then return
    flick = 0.5 + 0.25 * Sin(t * 9.1) + 0.25 * Sin(t * 14.3 + 1.7)
    if x.fire <> invalid
        ' Fourteen poses a second, cross-faded at the display rate.
        ph = t * 14.0
        i = Int(ph)
        mix = Int((ph - i) * alpha)
        n = x.fire.Count()
        screen.DrawObject(sx, c.fire.y, x.fire[i mod n], &hFFFFFF00 + alpha)
        if mix > 0 then screen.DrawObject(sx, c.fire.y, x.fire[(i + 1) mod n], &hFFFFFF00 + mix)
    end if
    if x.glows <> invalid and c.hearth <> invalid
        ' Firelight spilling over the hearth, breathing with the flames.
        k = 3.3 + 0.35 * flick
        a = Int((62 + 46 * flick) * alpha / 255)
        screen.DrawScaledObject(c.hearth[0] - s.camX - 32 * k, c.hearth[1] - 26 * k, k, k * 0.82, x.glows[5], &hFFFFFF00 + a)
    end if
end sub

sub ChristmasGlows(s as object, screen as object, gain as float)
    x = s.xmas
    if x.glows = invalid then return
    cam = s.camX
    lv = x.level
    for each b in x.bulbs
        sx = b.x - cam
        if sx > -40 and sx < 1960
            v = lv[b.g]
            a = Int(235 * v * gain)
            if a > 14
                k = 0.62 + 0.42 * v
                screen.DrawScaledObject(sx - 32 * k, b.y - 32 * k, k, k, x.glows[b.c], &hFFFFFF00 + a)
            end if
        end if
    end for
end sub
