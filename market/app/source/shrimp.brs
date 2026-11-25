' Peppermint shrimp: small cleaners that work their way along the sand and up over the rock.
'
' Each shrimp keeps to its own route, a line of points on the ground in tank coordinates. It
' walks a stretch, stops to pick the ground clean with one arm after the other, and walks on,
' turning round at the ends of its route and now and then in between. They are busier at
' night, as the real animal is.
'
' The frames (shrimp.png) are rendered facing right, standing on level ground, with their
' origin at the point on the ground under the body. On a slope a frame is turned about that
' point, as far as it takes: a route may climb straight up or curl back under an overhang. The
' shrimp's back stays on one side of the line all the way, the side that is up where the route
' is level, so a route drawn up the left edge of a reef keeps the animal out over the water.
' The walk clip is advanced by the distance walked, so the feet stay where they stand.
' The Roku cannot draw a sprite both flipped and turned (see fish.brs), so a shrimp heading
' left up or down a slope is drawn flipped into a scratch bitmap of its own, and that is turned.
'
' At night a shrimp also shows its glow: its red lines, leg joints, feelers and eyes, from a
' second sheet (shrimp_glow.png, laid out like the first at half its size) drawn over the dark.
'
' Scene config (cfg.shrimp): w, h and cols of the frame grid, anchor [x, y] inside a frame,
' walk { first, count, travel: px walked in one cycle }, clean { first, count, period },
' routes [{ pts: [[x, y], ...], shadow: true on sand and rock it can cast a shadow on }, ...].

sub ShrimpInit(s as object)
    s.shrimp = invalid
    c = s.cfg.shrimp
    if c = invalid then return
    tx = LoadTexture("pkg:/images/shrimp.png")
    if tx = invalid then return
    e = { cells: [], list: [], kx: tx.kx, ky: tx.ky }
    ' The soft blot the other critters use for a shadow, turned about its centre.
    e.blot = CreateObject("roRegion", s.puff, 0, 0, 24, 24)
    e.blot.SetPretranslation(-12, -12)
    e.blot.SetScaleMode(1)
    for i = 0 to c.walk.count + c.clean.count - 1
        e.cells.Push(AtlasRegion(tx, (i mod c.cols) * c.w, Int(i / c.cols) * c.h, c.w, c.h, Int(c.anchor[0] + 0.5), Int(c.anchor[1] + 0.5)))
    end for
    ' The scratch bitmap holds a flipped frame with the anchor at its centre.
    reach = c.anchor[0]
    if c.w - reach > reach then reach = c.w - reach
    e.scrW = 2 * Int(reach + 3)
    e.scrH = 2 * Int(c.anchor[1] + 3)
    for each r in c.routes
        cum = [0.0]
        total = 0.0
        for i = 1 to r.pts.Count() - 1
            dx = r.pts[i][0] - r.pts[i - 1][0] : dy = r.pts[i][1] - r.pts[i - 1][1]
            total = total + Sqr(dx * dx + dy * dy)
            cum.Push(total)
        end for
        sh = { pts: r.pts, cum: cum, len: total, d: Rnd(0) * total, dir: 1, seg: 0, mode: "walk", wait: RndRange(3, 10), tm: 0.0, turn: false }
        ' Which way the route runs overall: a shrimp walking it forward faces that way.
        sh.shadow = (r.shadow = true)
        sh.side = 1
        if r.pts[r.pts.Count() - 1][0] < r.pts[0][0] then sh.side = -1
        sh.speed = RndRange(13, 22) : sh.ph = Rnd(0) : sh.cph = 0.0 : sh.scr = invalid
        if Rnd(0) < 0.5 then sh.dir = -1
        ShrimpPlace(sh)
        sh.th = sh.aim
        e.list.Push(sh)
    end for
    s.shrimp = e
    LogMemory("shrimp")
end sub

sub ShrimpUpdate(s as object, t as float, dt as float)
    e = s.shrimp
    if e = invalid then return
    c = s.cfg.shrimp
    pace = 1 + 0.5 * s.night
    for each sh in e.list
        if sh.mode = "walk"
            walked = sh.speed * pace * dt
            sh.d = sh.d + sh.dir * walked
            sh.ph = sh.ph + walked / c.walk.travel
            sh.wait = sh.wait - dt
            ended = false
            if sh.d >= sh.len
                sh.d = sh.len
                ended = true
            else if sh.d <= 0
                sh.d = 0
                ended = true
            end if
            if ended or sh.wait <= 0
                sh.mode = "clean"
                sh.tm = RndRange(4, 10)
                sh.cph = 0.0
                ' At the end of the route it must turn back; elsewhere it sometimes does.
                sh.turn = ended or Rnd(0) < 0.2
            end if
        else
            sh.tm = sh.tm - dt * pace
            sh.cph = sh.cph + dt / c.clean.period
            if sh.tm <= 0
                if sh.turn then sh.dir = -sh.dir
                sh.mode = "walk"
                sh.wait = RndRange(5, 14)
                sh.speed = RndRange(13, 22)
            end if
        end if
        ShrimpPlace(sh)
        ' The body swings round to a new slope over a few steps, the short way.
        sh.th = ShrimpWrap(sh.th + ShrimpWrap(sh.aim - sh.th) * Clamp(4 * dt, 0, 1))
    end for
end sub

' An angle in degrees brought into -180 .. 180.
function ShrimpWrap(a as float) as float
    if a > 180 then return a - 360
    if a <= -180 then return a + 360
    return a
end function

' Where on its route a shrimp stands (x, y), which way it faces and how far it is turned.
sub ShrimpPlace(sh as object)
    i = sh.seg
    last = sh.pts.Count() - 2
    while i < last and sh.d > sh.cum[i + 1]
        i = i + 1
    end while
    while i > 0 and sh.d < sh.cum[i]
        i = i - 1
    end while
    sh.seg = i
    a = sh.pts[i] : b = sh.pts[i + 1]
    f = (sh.d - sh.cum[i]) / (sh.cum[i + 1] - sh.cum[i])
    sh.x = a[0] + (b[0] - a[0]) * f
    sh.y = a[1] + (b[1] - a[1]) * f
    dx = (b[0] - a[0]) * sh.dir
    dy = (b[1] - a[1]) * sh.dir
    sh.face = sh.side * sh.dir
    ' The way it is heading, in degrees anticlockwise from screen right. A frame faces right;
    ' flipped, it faces left, so it is turned half a circle less.
    if Abs(dx) < 0.001 then dx = 0.001
    heading = Atn(-dy / dx) * 57.29578
    if dx < 0 then heading = heading + 180
    if sh.face < 0 then heading = heading - 180
    sh.aim = ShrimpWrap(heading)
end sub

' Drawn with the other critters: over the reef pieces, behind the fish that swim in front.
sub ShrimpDraw(s as object, screen as object, t as float)
    e = s.shrimp
    if e = invalid then return
    ShrimpDrawFrom(s, screen, e, e.cells, e.kx, e.ky, "scr", &hFFFFFFFF)
end sub

' Loads the glow sheet, after everything else in the tank.
sub ShrimpGlowInit(s as object)
    e = s.shrimp
    if e = invalid then return
    e.glow = invalid
    c = s.cfg.shrimp
    tx = LoadTexture("pkg:/images/shrimp_glow.png")
    if tx = invalid then return
    pg = { bmp: tx.bmp, w: tx.w * 2, h: tx.h * 2, kx: tx.kx * 2, ky: tx.ky * 2 }
    e.glow = []
    for i = 0 to c.walk.count + c.clean.count - 1
        e.glow.Push(AtlasRegion(pg, (i mod c.cols) * c.w, Int(i / c.cols) * c.h, c.w, c.h, Int(c.anchor[0] + 0.5), Int(c.anchor[1] + 0.5)))
    end for
    e.gkx = pg.kx : e.gky = pg.ky
end sub

' After the night's dark has been laid over the tank: each shrimp's glow, pulsing a little.
sub ShrimpGlow(s as object, screen as object, t as float)
    e = s.shrimp
    if e = invalid then return
    if e.glow = invalid then return
    level = s.night
    if s.nightLite then level = 1.0
    if level < 0.04 then return
    a = Int(230 * level * (0.8 + 0.2 * Sin(t * 2.3)))
    ShrimpDrawFrom(s, screen, e, e.glow, e.gkx, e.gky, "gscr", &hFFFFFF00 + a)
end sub

' Draws every shrimp from one sheet's frames: cells scaled kx, ky, tinted col. A shrimp heading
' left on a slope goes through a scratch bitmap of its own, kept under the name `scratch`.
sub ShrimpDrawFrom(s as object, screen as object, e as object, cells as object, kx as float, ky as float, scratch as string, col as integer)
    c = s.cfg.shrimp
    body = (scratch = "scr")
    for each sh in e.list
        sx = sh.x - s.camX
        if sx > -180 and sx < 2100
            if sh.mode = "walk"
                p = sh.ph - Int(sh.ph)
                cell = cells[c.walk.first + Int(p * c.walk.count) mod c.walk.count]
            else
                p = sh.cph - Int(sh.cph)
                cell = cells[c.clean.first + Int(p * c.clean.count) mod c.clean.count]
            end if
            ' A soft shadow under the body, lying along the ground.
            if body and sh.shadow then screen.DrawTransformedObject(sx - 9 * sh.face, sh.y - 1, sh.th, 3.7, 0.42, e.blot, &h0A141E00 + 84)
            if sh.face > 0
                screen.DrawTransformedObject(sx, sh.y, sh.th, kx, ky, cell, col)
            else if Abs(sh.th) < 1.5 or not ShrimpFlipped(e, sh, cell, kx, ky, scratch)
                screen.DrawTransformedObject(sx, sh.y, 0, -kx, ky, cell, col)
            else
                screen.DrawTransformedObject(sx, sh.y, sh.th, 1, 1, sh[scratch].reg, col)
            end if
        end if
    end for
end sub

' Draws a frame flipped and level into the shrimp's scratch bitmap. False when there is no
' graphics memory for one (the shrimp is then drawn level).
function ShrimpFlipped(e as object, sh as object, cell as object, kx as float, ky as float, scratch as string) as boolean
    if sh[scratch] = invalid
        bmp = LoadBitmap({ width: e.scrW, height: e.scrH, AlphaEnable: true })
        if bmp = invalid then return false
        reg = CreateObject("roRegion", bmp, 0, 0, e.scrW, e.scrH)
        reg.SetPretranslation(-e.scrW / 2, -e.scrH / 2)
        sh[scratch] = { bmp: bmp, reg: reg }
    end if
    sh[scratch].bmp.Clear(0)
    sh[scratch].bmp.DrawTransformedObject(e.scrW / 2, e.scrH / 2, 0, -kx, ky, cell)
    return true
end function
