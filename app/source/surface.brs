' The 24 poses occupy one texture and share the camera's tank-space origin.
' Load after the fish so an optional water effect never displaces a species.
function LoadSurface(tankWidth as integer) as dynamic
    atlas = LoadBitmap(ImgPath("surface_ripple.jpg"))
    if atlas = invalid then return invalid
    frames = []
    height = Int(atlas.GetHeight() / 24)
    for i = 0 to 23
        region = CreateObject("roRegion", atlas, 0, i * height, atlas.GetWidth(), height)
        if region = invalid then return invalid
        region.SetScaleMode(1)
        frames.Push(region)
    end for
    return { frames: frames, scale: tankWidth / atlas.GetWidth() }
end function

sub DrawSurface(s as object, screen as object, t as float)
    if s.surface = invalid then return
    ' Vary the rate gently across cycles. Blend adjacent poses at display cadence.
    phase = t * 5.0 + 0.9 * Sin(t * 0.71)
    index = Int(phase)
    mix = Int((phase - index) * 255)
    scale = s.surface.scale
    frames = s.surface.frames
    screen.DrawScaledObject(-s.camX, 0, scale, scale, frames[index mod 24])
    if mix > 0
        screen.DrawScaledObject(-s.camX, 0, scale, scale, frames[(index + 1) mod 24], &hFFFFFF00 + mix)
    end if
end sub
