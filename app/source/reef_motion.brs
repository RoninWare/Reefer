' Decorative effects are loaded after the core reef and fish.
sub InitReefMotion(s as object)
    s.anemoneFrames = invalid
    atlas = LoadBitmap("pkg:/images/anemone_current.png")
    if atlas = invalid then return
    frames = []
    w = Int(atlas.GetWidth() / 4)
    h = Int(atlas.GetHeight() / 3)
    for i = 0 to 11
        region = CreateObject("roRegion", atlas, (i mod 4) * w, Int(i / 4) * h, w, h)
        if region = invalid then return
        region.SetScaleMode(1)
        frames.Push(region)
    end for
    s.anemoneFrames = frames
end sub

sub DrawReefMotion(s as object, screen as object, t as float)
    x = 1000 - s.camX
    if s.anemoneFrames <> invalid and x > -480 and x < 1920
        phase = t * 2.1 + 0.32 * Sin(t * 0.51)
        i = Int(phase)
        blend = Int(255 * (phase - i))
        scale = 10.0 / 7.0
        screen.DrawScaledObject(x, 500, scale, scale, s.anemoneFrames[i mod 12])
        if blend > 0
            screen.DrawScaledObject(x, 500, scale, scale, s.anemoneFrames[(i + 1) mod 12], &hFFFFFF00 + blend)
        end if
    end if
end sub
