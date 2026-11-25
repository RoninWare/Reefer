' Rellie Reef: adapted from Reef Glass v1.1.3 (Apache-2.0). What changed is listed in NOTICE.md.
sub init()
    m.order = ["lighting", "season"]
    m.focused = 0
    m.lists = {}
    m.ids = {}
    for each name in ["tank", "lighting", "season"]
        m.lists[name] = m.top.findNode(name)
        m.ids[name] = []
    end for
end sub

sub onTankChoices()
    if m.top.tankChoices.Count() < 2 then return
    fill("tank", m.top.tankChoices, "onTankChecked")
    m.top.findNode("tankLabel").visible = true
    m.lists.tank.visible = true
    m.top.findNode("lightingLabel").translation = [160, 391]
    m.lists.lighting.translation = [160, 437]
    m.top.findNode("seasonLabel").translation = [160, 764]
    m.lists.season.translation = [160, 810]
    m.order = ["tank", "lighting", "season"]
end sub

sub onLightingChoices()
    fill("lighting", m.top.lightingChoices, "onLightingChecked")
end sub

sub onSeasonChoices()
    fill("season", m.top.seasonChoices, "onSeasonChecked")
end sub

sub onReady()
    if m.top.settingsReady
        m.lists[m.order[m.focused]].setFocus(true)
        m.top.signalBeacon("AppLaunchComplete")
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

sub onTankSet()
    choose("tank", m.top.tank)
end sub

sub onLightingSet()
    choose("lighting", m.top.lighting)
end sub

sub onSeasonSet()
    choose("season", m.top.season)
end sub

' Show the saved pick without moving focus across lists.
sub choose(name as string, id as dynamic)
    list = m.lists[name]
    ids = m.ids[name]
    for i = 0 to ids.Count() - 1
        if ids[i] = id and list.checkedItem <> i
            list.checkedItem = i
            list.jumpToItem = i
        end if
    end for
end sub

sub onTankChecked()
    report("tank")
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
    nextList = m.focused
    if key = "down" then nextList = nextList + 1
    if key = "up" then nextList = nextList - 1
    if nextList = m.focused or nextList < 0 or nextList >= m.order.Count() then return false
    m.focused = nextList
    name = m.order[m.focused]
    index = 0
    if key = "up" then index = m.ids[name].Count() - 1
    m.lists[name].jumpToItem = index
    m.lists[name].setFocus(true)
    return true
end function
