' The green moray in his Santa hat, who lives in the reef's cave at Christmas.
'
' He is drawn from a sheet of rendered poses (santa_moray.png), each already in place in front
' of the cave, so there is nothing to assemble: this file only chooses which pose to show.
'
'   hidden   deep in the cave, only his snout catching the light
'   pop      shoots out, overshoots, hat and sack catching up: the "pop" clip, played by its
'            own timestamps (fast poses are shown as they are, slow ones cross-faded)
'   idle     sways, looks about and breathes: a seamless loop, cross-faded
'   settle   a short blend from wherever the loop is to the end of the pop clip
'   retreat  the pop clip run backward, faster
'
' A big fish swimming close sends him back in. When the Christmas
' reef is switched off (season.brs), or the sheet does not fit in graphics memory, the cave
' stands empty.
'
' Scene config (cfg.santaMoray): frames [[atlasX, atlasY, w, h, tankX, tankY], ...], popTimes,
' popBlendFrom, idleFirst, idleCount, idlePeriod, shade [x, y] for santa_cave.png.

sub SantaMorayInit(s as object)
    s.santa = invalid
    c = s.cfg.santaMoray
    tx = invalid
    if c <> invalid then tx = LoadTexture("pkg:/images/santa_moray.png")
    s.moray = invalid
    if tx = invalid then return
    e = { cells: [], shade: LoadBitmap("pkg:/images/santa_cave.png"), mode: "hidden", wait: RndRange(3, 6), tm: 0.0, ph: 0.0, loops: 0, from: 0, threatNow: false }
    for each f in c.frames
        e.cells.Push({ cell: XmasCell(tx, f[0], f[1], f[2], f[3]), x: f[4], y: f[5], w: f[2] })
    end for
    e.last = c.popTimes.Count() - 1
    e.popEnd = c.popTimes[e.last]
    s.santa = e
    LogMemory("santa moray")
end sub

sub SantaMorayUpdate(s as object, t as float, dt as float)
    e = s.santa
    if e = invalid then return
    c = s.cfg.santaMoray
    mc = s.cfg.moray
    if s.frame mod 3 = 0
        threat = false
        for each f in s.fish
            if f.big and f.z > s.cfg.fgZ - 0.2
                dx = f.x - mc.x : dy = f.y - mc.y
                if dx * dx + dy * dy < mc.threat * mc.threat
                    threat = true
                    exit for
                end if
            end if
        end for
        e.threatNow = threat
    end if

    if e.mode = "hidden"
        e.wait = e.wait - dt
        if e.wait <= 0 and not e.threatNow
            e.mode = "pop"
            e.tm = 0
        end if
    else if e.mode = "pop"
        e.tm = e.tm + dt
        if e.tm >= e.popEnd
            e.mode = "idle"
            e.ph = 0
            e.loops = 2 + Int(Rnd(0) * 4)
        end if
    else if e.mode = "idle"
        e.ph = e.ph + dt / c.idlePeriod
        if e.ph >= 1
            e.ph = e.ph - 1
            e.loops = e.loops - 1
        end if
        if e.threatNow or e.loops <= 0
            e.from = c.idleFirst + (Int(e.ph * c.idleCount + 0.5) mod c.idleCount)
            e.mode = "settle"
            e.tm = 0
            ' Startled, he stays in longer.
            e.wait = RndRange(7, 15)
            if e.threatNow then e.wait = RndRange(10, 18)
        end if
    else if e.mode = "settle"
        e.tm = e.tm + dt
        if e.tm >= 0.16
            e.mode = "retreat"
            e.tm = e.popEnd
        end if
    else
        e.tm = e.tm - dt * 1.7
        if e.tm <= 0
            e.tm = 0
            e.mode = "hidden"
        end if
    end if
end sub

sub SantaMorayDraw(s as object, screen as object, t as float)
    e = s.santa
    if e = invalid then return
    c = s.cfg.santaMoray
    a = 0 : b = 0 : mix = 0.0
    if e.mode = "pop" or e.mode = "retreat"
        ts = c.popTimes
        k = 0
        while k < e.last - 1 and ts[k + 1] <= e.tm
            k = k + 1
        end while
        u = (e.tm - ts[k]) / (ts[k + 1] - ts[k])
        if u > 1 then u = 1
        if u < 0 then u = 0
        a = k : b = k + 1 : mix = u
        ' Fast poses differ too much to blend: show the nearer one.
        if k < c.popBlendFrom
            if u >= 0.5 then a = b
            mix = 0
        end if
    else if e.mode = "idle"
        f = e.ph * c.idleCount
        k = Int(f)
        a = c.idleFirst + (k mod c.idleCount)
        b = c.idleFirst + ((k + 1) mod c.idleCount)
        mix = f - k
    else if e.mode = "settle"
        a = e.from : b = e.last : mix = e.tm / 0.16
        if mix > 1 then mix = 1
    end if
    ' Cross-fade without the body ever turning see-through: the outgoing pose stays solid
    ' while the incoming one fades in over it, then fades away underneath.
    if mix <= 0
        SantaMorayPose(s, screen, e.cells[a], 255)
    else if mix < 0.5
        SantaMorayPose(s, screen, e.cells[a], 255)
        SantaMorayPose(s, screen, e.cells[b], Int(510 * mix))
    else
        SantaMorayPose(s, screen, e.cells[a], Int(510 * (1 - mix)))
        SantaMorayPose(s, screen, e.cells[b], 255)
    end if
    ' The cave's back wall and shadow go over him, so his body runs off into the dark.
    if e.shade <> invalid then screen.DrawObject(c.shade[0] - s.camX, c.shade[1], e.shade)
end sub

sub SantaMorayPose(s as object, screen as object, p as object, alpha as integer)
    sx = p.x - s.camX
    if sx < 1920 and sx + p.w > 0 then XmasDrawCell(screen, p.cell, sx, p.y, alpha)
end sub
