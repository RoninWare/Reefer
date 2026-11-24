' Rellie Reef: adapted from Reef Glass v1.1.3 (Apache-2.0). What changed is listed in NOTICE.md.
' Two radio lists, lighting above season. Picking an entry reports it at once (the main
' thread saves it), and Back reports done. Each list is known by the name of its field.

sub init()
    m.lists = { lighting: m.top.findNode("lighting"), season: m.top.findNode("season") }
    m.ids = { lighting: [], season: [] }
    m.focused = "lighting"
    m.lists.lighting.setFocus(true)
end sub

sub onLightingChoices()
    fill("lighting", m.top.lightingChoices, "onLightingChecked")
end sub

sub onSeasonChoices()
    fill("season", m.top.seasonChoices, "onSeasonChecked")
    ' Both lists are filled and the screen is fully shown: tell Roku the launch is complete
    ' (certification 3.2 measures launch time with this beacon).
    if m.launched <> true
        m.top.signalBeacon("AppLaunchComplete")
        m.launched = true
    end if
end sub

' The choices arrive from the main thread before the saved pick. A list reports picks only
' once it is filled and set to the saved pick, so filling it never reports (and saves) its
' first entry.
sub fill(name as string, choices as object, callback as string)
    list = m.lists[name]
    ids = []
    root = CreateObject("roSGNode", "ContentNode")
    for each c in choices
        ids.Push(c.id)
        item = root.createChild("ContentNode")
        item.title = c.label
    end for
    m.ids[name] = ids
    list.unobserveField("checkedItem")
    list.content = root
    list.checkedItem = 0
    choose(name, m.top.getField(name))
    list.observeField("checkedItem", callback)
end sub

sub onLightingSet()
    choose("lighting", m.top.lighting)
end sub

sub onSeasonSet()
    choose("season", m.top.season)
end sub

' Shows a saved pick in its list. The picks arrive after init, once the screen is shown; focus
' set in init can be lost by then, so the list that should have it takes it again here.
sub choose(name as string, id as dynamic)
    if not m.lists[m.focused].hasFocus() then m.lists[m.focused].setFocus(true)
    list = m.lists[name]
    ids = m.ids[name]
    for i = 0 to ids.Count() - 1
        if ids[i] = id and list.checkedItem <> i
            list.checkedItem = i
            list.jumpToItem = i
        end if
    end for
end sub

sub onLightingChecked()
    report("lighting")
end sub

sub onSeasonChecked()
    report("season")
end sub

sub report(name as string)
    i = m.lists[name].checkedItem
    ids = m.ids[name]
    if i >= 0 and i < ids.Count() and m.top.getField(name) <> ids[i] then m.top.setField(name, ids[i])
end sub

' A list keeps Up and Down while it can still move; at its end the key arrives here, and
' focus steps into the other list.
function onKeyEvent(key as string, press as boolean) as boolean
    if not press then return false
    if key = "back"
        m.top.done = true
        return true
    end if
    if key = "down" and m.focused = "lighting"
        m.focused = "season"
        m.lists.season.jumpToItem = 0
        m.lists.season.setFocus(true)
        return true
    end if
    if key = "up" and m.focused = "season"
        m.focused = "lighting"
        m.lists.lighting.jumpToItem = m.ids.lighting.Count() - 1
        m.lists.lighting.setFocus(true)
        return true
    end if
    return false
end function
