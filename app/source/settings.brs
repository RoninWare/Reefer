' Rellie Reef: adapted from Reef Glass v1.1.3 (Apache-2.0). What changed is listed in NOTICE.md.
' Screensaver settings: the tank's lighting, held at daytime (the default), dusk or night, or
' following the Roku's clock; and the season, the Christmas reef (the default) or the everyday
' one. Roku opens RunScreenSaverSettings from the screensaver's "Change screensaver settings"
' entry. That context only shows SceneGraph screens, so the UI is
' components/SettingsScene.xml; this side loads the saved choices into it and saves each back
' to the registry as soon as it changes. A change shows the next time the screensaver starts.

' Lighting choices, in list order, with the tank hour each one holds (auto: the clock).
function LightingChoices() as object
    return [
        { id: "auto", label: "Follow the Roku's clock" }
        { id: "day", label: "Daytime", hour: 12.0 }
        { id: "dusk", label: "Dusk", hour: 20.7 }
        { id: "night", label: "Night", hour: 23.0 }
    ]
end function

' Season choices, in list order (see season.brs for what the Christmas reef adds).
function SeasonChoices() as object
    return [
        { id: "christmas", label: "Christmas reef" }
        { id: "plain", label: "Everyday reef" }
    ]
end function

' A saved choice, or the fallback when nothing valid is saved.
function LoadSetting(key as string, choices as object, fallback as string) as string
    reg = CreateObject("roRegistrySection", "rellieReef")
    id = fallback
    if reg.Exists(key) then id = reg.Read(key)
    for each c in choices
        if c.id = id then return id
    end for
    return fallback
end function

sub SaveSetting(key as string, id as string)
    reg = CreateObject("roRegistrySection", "rellieReef")
    reg.Write(key, id)
    reg.Flush()
end sub

function LoadLighting() as string
    return LoadSetting("lighting", LightingChoices(), "day")
end function

function LoadSeason() as string
    return LoadSetting("season", SeasonChoices(), "christmas")
end function

' The hour to hold the tank at for a lighting choice, or invalid to follow the clock.
function LightingHour(id as string) as dynamic
    for each c in LightingChoices()
        if c.id = id and c.hour <> invalid then return c.hour
    end for
    return invalid
end function

sub RunScreenSaverSettings()
    screen = CreateObject("roSGScreen")
    port = CreateObject("roMessagePort")
    screen.SetMessagePort(port)
    mon = StartMemoryMonitor(port)
    ui = screen.CreateScene("SettingsScene")
    screen.Show()
    ' Choices first, then the saved picks: the scene reports a pick only once its list is
    ' filled and set, so filling a list never saves its first entry.
    ui.lightingChoices = LightingChoices()
    ui.seasonChoices = SeasonChoices()
    ui.lighting = LoadLighting()
    ui.season = LoadSeason()
    ui.ObserveField("lighting", port)
    ui.ObserveField("season", port)
    ui.ObserveField("done", port)
    while true
        msg = wait(0, port)
        t = type(msg)
        if t = "roDeviceInfoEvent" or t = "roAppMemoryNotificationEvent" then HandleMemoryEvent(msg)
        if t = "roSGNodeEvent" and msg.GetField() = "lighting"
            SaveSetting("lighting", ui.lighting)
            print "SETTINGS saved lighting="; ui.lighting
        end if
        if t = "roSGNodeEvent" and msg.GetField() = "season"
            SaveSetting("season", ui.season)
            print "SETTINGS saved season="; ui.season
        end if
        if (t = "roSGNodeEvent" and msg.GetField() = "done") or (t = "roSGScreenEvent" and msg.IsScreenClosed())
            SaveSetting("lighting", ui.lighting)
            SaveSetting("season", ui.season)
            return
        end if
    end while
end sub
