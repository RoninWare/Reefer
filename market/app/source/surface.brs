' The 24 poses occupy one texture and share the camera's tank-space origin. The store edition
' keeps them at a quarter of the tank's scale and draws them four times as large.
' Load after the fish so an optional water effect never displaces a species.
function LoadSurface() as dynamic
    atlas = LoadBitmap("pkg:/images/surface_ripple.jpg")
    if atlas = invalid then return invalid
    frames = []
    height = Int(atlas.GetHeight() / 24)
    for i = 0 to 23
        region = CreateObject("roRegion", atlas, 0, i * height, atlas.GetWidth(), height)
        if region = invalid then return invalid
        region.SetScaleMode(1)
        frames.Push(region)
    end for
    return frames
end function

sub DrawSurface(s as object, screen as object, t as float)
    if s.surface = invalid then return
    ' Vary the rate gently across cycles. Blend adjacent poses at display cadence.
    phase = t * 5.0 + 0.9 * Sin(t * 0.71)
    index = Int(phase)
    mix = Int((phase - index) * 255)
    screen.DrawScaledObject(-s.camX, 0, 4.0, 4.0, s.surface[index mod 24])
    if mix > 0
        screen.DrawScaledObject(-s.camX, 0, 4.0, 4.0, s.surface[(index + 1) mod 24], &hFFFFFF00 + mix)
    end if
end sub
