#!/usr/bin/env python3
# Copyright (c) 2016-2020, henry232323
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

from datetime import datetime
import re
import os

from PyQt5.QtGui import QPalette


def color_to_span(msg):
    """Convert <c=#hex> codes to <span style="color:"> codes"""
    exp = r'<c=(.*?)>(.*?)</c>'
    subexp = r'(?<=<c=).*?(?=>)'
    hexcodes = re.sub(subexp, isrgb, msg)
    rep = r'<span style="color:\1">\2</c>'
    colors = re.sub(exp, rep, hexcodes)
    colors = re.sub('</c>', '</span>', colors)
    return colors


def fmt_begin_msg(app, fromuser, touser):
    """Format a PM begin message"""
    msg = "/me began pestering {touser} {toInit} at {time}".format(touser=touser.display_name,
                                                                   toInit=getInitials(app, touser,
                                                                                      c=True), time=getTime(app))
    return fmt_me_msg(app, msg, fromuser)


def fmt_cease_msg(app, fromuser, touser):
    """Format a PM cease message"""
    msg = "/me ceased pestering {touser} {toInit} at {time}".format(touser=touser, toInit=getInitials(app, touser,
                                                                                                      c=True),
                                                                    time=getTime(app))
    return fmt_me_msg(app, msg, fromuser)


def fmt_mood_msg(app, mood, user):
    fmt = "/me changed their mood to {} {}"
    path = os.path.join(app.theme["path"], mood.lower() + ".png")
    img = fmt_img(path)
    msg = fmt.format(mood.upper(), img)
    return fmt_me_msg(app, msg, user)


def fmt_me_msg(app, msg, user, time=False):
    """Format a /me style message i.e.  -- ghostDunk's [GD'S] cat says hi -- (/me's cat says hi)"""
    me = msg.split()[0]
    suffix = me[3:]
    init = getInitials(app, user, c=True, suffix=suffix)
    predicate = msg[3 + len(suffix):].strip()
    timefmt = '<span style="color:black;">[{}]</style>'.format(getTime(app)) if time else ""
    fmt = '<b>{timefmt}<span style="color:#646464;"> -- {user}{suffix} {init} {predicate}--</span></b><br />'
    msg = fmt.format(user=user.display_name, init=init,
                     timefmt=timefmt if app.options["conversations"]["time_stamps"] else "", predicate=predicate,
                     suffix=suffix)
    return msg

html_escape_table = {
    "&": "&amp;",
    '"': "&quot;",
    "'": "&apos;",
    ">": "&gt;",
    "<": "&lt;",
    }

def html_escape(text):
    """Produce entities within text."""
    return "".join(html_escape_table.get(c,c) for c in text)


def fmt_disp_msg(app, msg, mobj, user=None):
    """Format a message for display"""
    msg = html_escape(msg)
    if not user:
        user = app.nick
    # If /me message, use fmt_me_msg
    elif msg.startswith("/me"):
        msg = fmt_me_msg(app, msg, user, time=True)
    # Otherwise convert <c> to <span> and format normally with initials etc
    else:
        msg = color_to_span(msg)
        time = format_time(app, mobj)
        init = getInitials(app, user, b=False)
        color = app.getColor(user)
        bgcolor = app.gui.palette().color(QPalette.Background)
        bgluma = 0.2126 * bgcolor.red() + 0.7152 * bgcolor.green() + 0.0722 * bgcolor.blue()
        r, g, b = parse_rgb_literal(color)
        colorluma = 0.2126 * r + 0.7152 * g + 0.0722 * b
        if bgluma < 40 and colorluma < 40:
            color = f"#{hex(int(r * 1.5))}{hex(int(g * 1.5))}{hex(int(g * 1.5))}"

        if bgluma > 215 and colorluma > 215:
            color = f"#{hex(r // 1.5)}{hex(g // 1.5)}{hex(g // 1.5)}"

        fmt = '<b><span style="color:black;">{time} <span style="color:{color};">{init}: {msg}</span></span></b><br />'
        msg = fmt.format(time="[" + time + "]" if app.options["conversations"]["time_stamps"] else "", init=init,
                         msg=msg.strip(), color=color)
        msg = app.emojis.process_emojis(msg, mobj)
        msg = app.mentions.process_mentions(msg, mobj)
        if str(msg).find("|") != -1:
            ## -- Spoiler tag magic -- ##
            # TODO: define these variables somehwere that isn't here
            tempMessage = ""
            modifiedMessage = ""
            spoileredLastSplit = False
            # pipeLocations are non-escaped double pipes ||
            allPipeLocations = [i for i in range(len(msg)) if msg.startswith("||", i)]

            # escapedPipeLocations are escaped double pipes \||
            # these shouldn't be made into spoiler tags under any circumstance, and must be ignored
            escapedPipeLocations = [i for i in range(len(msg)) if msg.startswith("\||", i-1)]

            # accounting for someone doing more than 2 | in a row (e.g |||)
            # discord uses the first ||, ie |||text||| -> <spoiler>|</spoiler>|
            # TODO: when input is ||||||, the output is not like discords:
            # discord will output <spoiler>|</spoiler>| but this outputs |||||| (no valid pipe pairs)
            extraPipeLocations = [i for i in range(len(msg)) if msg.startswith("|||", i-1)]

            # To ignore escaped pipes, we remove any escapedPipeLocations from allPipeLocations
            # These are valid instances of ||, but aren't start or end points of a spoiler tag
            # we also ignore extra pipes, so the spoilered text behaves like discord's
            validPipeLocations = list(set(allPipeLocations) - set(escapedPipeLocations) - set(extraPipeLocations))

            # Because Discord spoilers between *pairs* of double pipes, we want an even number of them
            # So, if validPipeLocations is odd, we remove the last location
            # This checks if len(validPipeLocations) / 2 has a remainder, as odd numbers will but even numbers won't
            if len(validPipeLocations) % 2 == 0:
            # all valid locations are also spoiler tag locations
                spoilerPipeLocations = validPipeLocations
            else:
            # removes last ||, as it's not part of a valid spoiler tag
                spoilerPipeLocations = validPipeLocations[:-1]

            print("All instances of || are:             " + str(allPipeLocations))
            print("All escaped instances are:           " + str(escapedPipeLocations))
            print("All instances of ||| are:            " + str(extraPipeLocations))
            print("All non-escaped instances of || are: " + str(validPipeLocations))
            print("All pipe pairs / spoiler tags are:   " + str(spoilerPipeLocations))
                    
            for i in range(len(spoilerPipeLocations)):
                # if start of message, split from start of message to first spoiler tag
                if i == 0:
                    modifiedMessage = msg[:spoilerPipeLocations[i]]
                    print("Splitting from start of message, to first spoiler tag.")
                    spoileredLastSplit = False

                # if last spoiler pipe in message, split from last spoiler tag to end of message
                if i == (len(spoilerPipeLocations)-1):
                    tempMessage = msg[(spoilerPipeLocations[i]+2):]
                    
                    # if last split was plaintext, this split is spoilered
                    if spoileredLastSplit == False:
                        spoileredLastSplit = True
                        modifiedMessage = modifiedMessage + "<div class=\"spoiler\">" + str(tempMessage) + "</div>"
                    # if last split was spoilered, this split is plaintext
                    else:
                        modifiedMessage = modifiedMessage + tempMessage
                        spoileredLastSplit = False
                    print("Splitting from last spoiler tag, to end of message.")
                        
                # else split from i'th spoiler tag to i+1'th spoiler tag    
                else:
                    tempMessage = msg[(spoilerPipeLocations[i]+2):spoilerPipeLocations[i+1]]
                    # if last split was plaintext, this split is spoilered
                    if spoileredLastSplit == False:
                        spoileredLastSplit = True
                        modifiedMessage = modifiedMessage + "<div class=\"spoiler\">" + str(tempMessage) + "</div>"
                    # if last split was spoilered, this split is plaintext
                    else:
                        modifiedMessage = modifiedMessage + tempMessage
                        spoileredLastSplit = False
                    print("Splitting from character " + str(spoilerPipeLocations[i]) + " to character " + str(spoilerPipeLocations[i+1]))


            if (len(spoilerPipeLocations) == 0):
                print("No spoilering needs to happen :)")
            msg = modifiedMessage
            print("\n\n Input Message: " + msg)
            print("Output Message: " + msg)

    return msg


def fmt_img(src):
    return '<img src="{}"/>'.format(src)


def fmt_color(color):
    """Format a color message"""
    if type(color) == tuple:
        return "COLOR >{},{},{}".format(*color)
    else:
        return "COLOR >{},{},{}".format(*rgb(color, type=tuple))


def getInitials(app, user, b=True, c=False, suffix=None, prefix=None):
    """
    Get colored or uncolored, bracketed or unbracketed initials with
    or without a suffix using a Chumhandle. A suffix being a me style
    ending. i.e. /me's [GD'S]
    """
    nick = user.display_name
    init = nick[0].upper()
    for char in nick:
        if char.isupper():
            break
    init += char.upper()
    if suffix:
        init += suffix
    if prefix:
        init = prefix + init
    if b:
        fin = "[" + init + "]"
    else:
        fin = init
    if c:
        fin = '<span style="color:{color}">{fin}</span>'.format(fin=fin, color=app.getColor(user))
    return fin


def rgbtohex(r, g, b):
    '''Convert RGB values to hex code'''
    return '#%02x%02x%02x' % (r, g, b)


def parse_rgb_literal(color):
    if color.startswith("#"):
        return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    color = color.strip("()rgb")
    colors = color.split(",")
    return int(colors[0].strip(), 16), int(colors[1].strip(), 16), int(colors[2].strip(), 16)


def isrgb(match):
    '''Checks if is RGB, formats CSS rgb func'''
    s = match.group(0)
    if s.startswith("#"):
        return rgb(s)
    elif s.startswith("rgb"):
        return s
    else:
        return "rgb(" + s.strip('rgb()') + ")"


def rgb(triplet, type=str):
    '''Converts hex triplet to RGB value tuple or string'''
    if hasattr(triplet, "group"):
        triplet = triplet.group(0)
    triplet = triplet.strip("#")
    digits = '0123456789abcdefABCDEF'
    hexdec = {v: int(v, 16) for v in (x + y for x in digits for y in digits)}
    if type == str:
        return "rgb" + str((hexdec[triplet[0:2]], hexdec[triplet[2:4]], hexdec[triplet[4:6]]))
    else:
        return hexdec[triplet[0:2]], hexdec[triplet[2:4]], hexdec[triplet[4:6]]


def getTime(app):
    '''Get current time in UTC based off settings'''
    time = datetime.utcnow()
    if app.options["conversations"]["show_seconds"]:
        fmt = "{hour}:{minute}:{sec}"
    else:
        fmt = "{hour}:{minute}"
    ftime = fmt.format(
        hour=str(time.hour).zfill(2),
        minute=str(time.minute).zfill(2),
        sec=str(time.second).zfill(2))
    return ftime


def format_time(app, message):
    time = message.created_at
    if app.options["conversations"]["show_seconds"]:
        fmt = "{hour}:{minute}:{sec}"
    else:
        fmt = "{hour}:{minute}"
    ftime = fmt.format(
        hour=str(time.hour).zfill(2),
        minute=str(time.minute).zfill(2),
        sec=str(time.second).zfill(2))
    return ftime


def fmt_color_wrap(msg, color):
    fmt = "<span style=\"color:{color}\">{msg}</span>"
    return fmt.format(msg=msg, color=color)


def fmt_memo_msg(app, msg, user):
    return "<c={color}>{initials}: {msg}</c>".format(
        initials=getInitials(app, user, b=False, c=False),
        color=app.getColor(user),
        msg=msg)


def fmt_disp_memo(app, message, user, prefix=""):
    msg = "<b><span color={color}>{msg}</span><b><br />".format(
        prefix=prefix,
        msg=color_to_span(message),
        color=app.getColor(user))
    return msg


def fmt_memo_join(app, user, time, memo, part=False, opened=False):
    if part:
        type = "ceased responding to memo."
    elif opened:
        type = "opened memo on board {}.".format(memo.name)
    else:
        type = "responded to memo."
    if time[0] == "i":
        frame = "CURRENT"
        fmt = "<b>{clr} <span style=\"color:#646464\">RIGHT NOW {type}</span></b><br />"
        pfx = "C"
        timefmt = ""

    else:
        hours, minutes = time.split(":")
        hours, minutes = int(hours), int(minutes)
        if time[0] == "F":
            frame = "FUTURE"
            if hours:
                timefmt = "{}:{} HOURS FROM NOW".format(hours, minutes)
            else:
                timefmt = "{} MINUTES FROM NOW".format(minutes)
        elif time[0] == "P":
            frame = "PAST"
            if hours:
                timefmt = "{}:{} HOURS AGO".format(hours, minutes)
            else:
                timefmt = "{} MINUTES AGO".format(minutes)
        pfx = time[0]
        fmt = "<b>{clr} <span style=\"color:#646464\">{time} {type}</span></b><br />"

    colorfmt = "<span style=\"color:{color}\">{frame} {user} {binit}</span>"
    clr = colorfmt.format(color=app.getColor(user),
                          frame=frame,
                          user=user,
                          binit=getInitials(app, user, prefix=pfx))

    fin = fmt.format(clr=clr, time=timefmt, type=type)
    return fin
