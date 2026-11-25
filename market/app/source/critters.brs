' Rellie Reef: adapted from Reef Glass v1.1.3 (Apache-2.0). What changed is listed in NOTICE.md.
' Reef critters: feather duster worms and a starfish, where the scene has them (the store
' edition's reef has neither yet). The cave's moray is drawn here but lives in santa_moray.brs.

sub CrittersInit(s as object)
    cfg = s.cfg
    s.dusters = []
    if cfg.dusters <> invalid and cfg.dusters.Count() > 0
        s.crown = CreateObject("roBitmap", "pkg:/images/duster_crown.png")
        s.tube = CreateObject("roBitmap", "pkg:/images/duster_tube.png")
        k = 0
        for each d in cfg.dusters
            s.dusters.Push({ x: d.x, y: d.y, s: d.s, open: 1.0, mode: "open", wait: 0, cool: 0, ph: k * 1.9 })
            k = k + 1
        end for
        if s.crown = invalid or s.tube = invalid then s.dusters = []
    end if

    s.star = invalid
    sf = cfg.starfish
    if sf <> invalid
        s.starBmp = CreateObject("roBitmap", "pkg:/images/starfish.png")
        if s.starBmp <> invalid then s.star = { x: RndRange(sf.x0, sf.x1), dir: 1, rest: 0 }
    end if

    s.puff = CreateObject("roBitmap", "pkg:/images/puff.png")
    ' The moray loads after the fish (SantaMorayInit, called from ReefInit).
    s.moray = invalid
    s.santa = invalid
end sub

sub CrittersUpdate(s as object, t as float, dt as float)
    SantaMorayUpdate(s, t, dt)
    UpdateDusters(s, t, dt)
    ' Starfish: a very slow glide back and forth along the sand on its tube feet (real sea
    ' stars cover a few cm a minute), resting at each end.
    st = s.star
    if st = invalid then return
    sf = s.cfg.starfish
    if st.rest > 0
        st.rest = st.rest - dt
    else
        st.x = st.x + st.dir * sf.speed * s.activity * dt
        if st.x > sf.x1 or st.x < sf.x0
            st.dir = -st.dir
            st.x = Clamp(st.x, sf.x0, sf.x1)
            st.rest = RndRange(20, 60)
        end if
    end if
end sub

' Drawn after the night's dark, in its tint (s.dim).
sub CrittersDraw(s as object, screen as object, t as float)
    ' Starfish, with a soft contact shadow so it sits on the sand.
    st = s.star
    if st <> invalid
        sw = s.starBmp.GetWidth() : shh = s.starBmp.GetHeight()
        sy = s.cfg.starfish.y
        sx = st.x - s.camX
        screen.DrawScaledObject(sx - sw * 0.55, sy - shh * 0.2, sw * 1.1 / 24, shh * 0.9 / 24, s.puff, &h1A140F00 + 90)
        screen.DrawObject(sx - sw / 2, sy - shh / 2, s.starBmp, s.dim)
    end if

    ' The moray's cave shade covers rock around the cave; the dusters growing on that rock go
    ' over it.
    SantaMorayDraw(s, screen, t)
    DrawDusters(s, screen, t)
end sub

' Feather dusters snap shut when a fish swims close, then unfurl slowly. They are checked
' against the fish every fourth frame.
sub UpdateDusters(s as object, t as float, dt as float)
    for each d in s.dusters
        if d.mode = "closing"
            d.open = d.open - dt / 0.15
            if d.open <= 0.04
                d.open = 0.04
                d.mode = "closed"
                d.wait = RndRange(3, 9)
            end if
        else if d.mode = "closed"
            d.wait = d.wait - dt
            if d.wait <= 0 then d.mode = "opening"
        else if d.mode = "opening"
            d.open = d.open + dt / 3.0
            if d.open >= 1
                d.open = 1
                d.mode = "open"
                ' Once open again it tolerates passing fish for a while.
                d.cool = RndRange(10, 30)
            end if
        else
            d.cool = d.cool - dt
        end if
    end for
    if s.frame mod 4 <> 0 then return
    for each d in s.dusters
        if d.mode = "open" and d.cool <= 0
            for each f in s.fish
                dx = f.x - d.x : dy = f.y - (d.y - 40)
                r = 70 + 60 * f.size * f.z
                if dx * dx + dy * dy < r * r and Rnd(0) < 0.35
                    d.mode = "closing"
                    exit for
                end if
            end for
        end if
    end for
end sub

sub DrawDusters(s as object, screen as object, t as float)
    if s.dusters.Count() = 0 then return
    cw = s.crown.GetWidth() : ch = s.crown.GetHeight()
    tw = s.tube.GetWidth()
    drop = 0
    if s.cfg.duster <> invalid then drop = s.cfg.duster.crownDrop
    for each d in s.dusters
        if d.open > 0.05
            ' Retracting: the crown shrinks down into the tube mouth; open crowns breathe a little.
            k = d.open
            sx = d.s * (0.3 + 0.7 * k) * (1 + 0.04 * Sin(t * 0.9 + d.ph))
            sy = d.s * k
            screen.DrawScaledObject(d.x - s.camX - sx * cw / 2 + 2 * Sin(t * 0.6 + d.ph), d.y - sy * (ch - drop), sx, sy, s.crown, s.dim)
        end if
        screen.DrawScaledObject(d.x - s.camX - d.s * tw / 2, d.y - 4 * d.s, d.s, d.s, s.tube, s.dim)
    end for
end sub

