' Preview canvas uses 720p. Scene coordinates and fish scratch bitmaps use the original units.
sub PreviewObject(target as object, x as float, y as float, sprite as object, color = &hFFFFFFFF as integer)
    PreviewScaled(target, x, y, 1.0, 1.0, sprite, color)
end sub

sub PreviewScaled(target as object, x as float, y as float, sx as float, sy as float, sprite as object, color = &hFFFFFFFF as integer)
    if Type(target) = "roScreen"
        k = 2.0 / 3.0
        target.DrawScaledObject(x * k, y * k, sx * k, sy * k, sprite, color)
    else
        target.DrawScaledObject(x, y, sx, sy, sprite, color)
    end if
end sub

sub PreviewRotated(target as object, x as float, y as float, angle as float, sprite as object, color = &hFFFFFFFF as integer)
    PreviewTransformed(target, x, y, angle, 1.0, 1.0, sprite, color)
end sub

sub PreviewTransformed(target as object, x as float, y as float, angle as float, sx as float, sy as float, sprite as object, color = &hFFFFFFFF as integer)
    if Type(target) = "roScreen"
        k = 2.0 / 3.0
        target.DrawTransformedObject(x * k, y * k, angle, sx * k, sy * k, sprite, color)
    else
        target.DrawTransformedObject(x, y, angle, sx, sy, sprite, color)
    end if
end sub

sub PreviewRect(target as object, x as float, y as float, width as float, height as float, color as integer)
    k = 2.0 / 3.0
    target.DrawRect(x * k, y * k, width * k, height * k, color)
end sub
