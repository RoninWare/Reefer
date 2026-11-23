' The season switch. The packaged scene (scenes/tank.json) describes the Christmas reef:
' its fireplace and gifts are reef pieces marked "xmas", its lights, fire and bubbles are
' under "christmas", and the Santa moray under "santaMoray". When the Christmas reef is
' switched off (settings.brs), those parts are removed from the scene before anything is
' loaded, so none of their pictures ever take up graphics memory:
'
'   - marked pieces are dropped from the tank;
'   - the fish steer by the coral map made without them ("coralPlain");
'   - with "christmas" gone, christmas.brs draws nothing;
'   - with "santaMoray" gone, the snowflake moray keeps the cave (santa_moray.brs).

sub ApplySeason(cfg as object, christmas as boolean)
    if christmas then return
    pieces = []
    for each p in cfg.pan.pieces
        if p.xmas <> true then pieces.Push(p)
    end for
    cfg.pan.pieces = pieces
    if cfg.coral <> invalid and cfg.coralPlain <> invalid then cfg.coral.rows = cfg.coralPlain
    cfg.Delete("christmas")
    cfg.Delete("santaMoray")
end sub
