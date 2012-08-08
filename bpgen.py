#!/usr/bin/env python3
# -*- coding: utf8 -*-
################################################################################
##
## Copyright (C) 2012 Typhos
##
## This Source Code Form is subject to the terms of the Mozilla Public
## License, v. 2.0. If a copy of the MPL was not distributed with this
## file, You can obtain one at http://mozilla.org/MPL/2.0/.
##
################################################################################

import argparse
import re
import sys
import time

import yaml

# A note on case: emote names are case-sensitive, but CSS is not. Rather than
# check case, we assume that emotes of different cases are the same (there's
# only one right now anyway, and it is).

AutogenHeader = """
/*
 * This file is AUTOMATICALLY GENERATED. DO NOT EDIT.
 * Generated at %s.
 */

""" % (time.strftime("%c"))

def make_selector(name):
    # For colored text things... as a TODO we could replace all non-valid chars
    # with e.g. their ord() numbers
    name = name.replace("!", "_excl_")
    return ".bpmotes-%s" % (name.lstrip("/"))

class Emote(object):
    def __init__(self, filename, name, properties, css):
        props = properties.copy()
        assert name.startswith("/")

        self.filename = filename
        # Don't normalize case here
        self.name = name
        self.css = css
        self.ignore = props.pop("Ignore", False)
        self.nsfw = props.pop("NSFW", False)
        self.nocss = props.pop("NoCSS", False)
        self.nomap = props.pop("NoMap", False)
        # Normalize case for CSS
        self.selector = props.pop("Selector", make_selector(name.lower()))
        self.css.update(props.pop("CSS", {}))

        for (key, val) in props.items():
            print("WARNING: Unknown key %r on %s in %s (= %r)" % (key, name, filename, val))

def process_spritesheet(filename, image_url, emotes):
    all_emotes = []

    for (name, props) in emotes.items():
        (width, height, x_pos, y_pos) = props.pop("Positioning")
        css = {
            "display": "block",
            "clear": "none",
            "float": "left",
            "background-image": "url(%s)" % (image_url),
            "width": px(width),
            "height": px(height),
            "background-position": "%s %s" % (px(x_pos), px(y_pos))
            }
        all_emotes.append(Emote(filename, name, props, css))

    return all_emotes

def px(s):
    return "%spx" % (s)

def process_file(filename, data):
    all_emotes = []

    for (image_url, emotes) in data.pop("Spritesheets", {}).items():
        all_emotes.extend(process_spritesheet(filename, image_url, emotes))

    for (name, props) in data.pop("Custom", {}).items():
        all_emotes.append(Emote(filename, name, props, {}))

    for section in data:
        print("WARNING: Unknown section %s in %s" % (section, filename))

    return all_emotes

def build_data(emotes):
    css_rules = {}
    nsfw_css_rules = {}
    js_map = {}

    for emote in emotes:
        if emote.ignore:
            continue

        rules = nsfw_css_rules if emote.nsfw else css_rules
        if not emote.nocss:
            if emote.selector in rules:
                print("Conflicting selector:", emote.selector)
            assert emote.selector not in rules
            rules[emote.selector] = emote.css.copy()

        if not emote.nomap:
            assert emote.name not in js_map
            js_map[emote.name] = emote.selector.lstrip(".")

    return css_rules, nsfw_css_rules, js_map

def simplify(rules):
    # Locate all known CSS properties, and sort selectors by their value
    properties = {}
    for (selector, props) in rules.items():
        for (prop_name, prop_value) in props.items():
            properties.setdefault(prop_name, {}).setdefault(prop_value, []).append(selector)

    def condense(prop_name, value, which=None):
        # Add new, combined rule
        selectors = which or properties.get(prop_name, {}).get(value, [])
        props = rules.setdefault(",".join(selectors), {})
        assert prop_name not in props
        props[prop_name] = value

        # Delete from old ones
        for selector in selectors:
            rules[selector].pop(prop_name)

    # TODO: Would be nice to automatically seek out stuff we can efficiently
    # collapse, but for now, this achieves great gains for little complexity.

    # Pass 1: condense the common stuff
    condense("display", "block")
    condense("clear", "none")
    condense("float", "left")

    # A lot of emotes are 70px square, though this only gets us about 35kb
    w70 = set(properties.get("width", {}).get("70px", []))
    h70 = set(properties.get("height", {}).get("70px", []))
    subset = w70.intersection(h70)
    condense("width", "70px", subset)
    condense("height", "70px", subset)

    # Pass 2: condense multi-emote spritesheets
    for (image_url, selectors) in properties.get("background-image", {}).items():
        if len(selectors) > 1:
            condense("background-image", image_url)

    # Pass 3: remove all useless background-position's
    for selector in properties.get("background-position", {}).get("0px 0px", []):
        rules[selector].pop("background-position")

    # Pass 4: remove all empty rules (not that there are many)
    for (selector, props) in list(rules.items()): # can't change dict while iterating
        if not props:
            rules.pop(selector)

def format_rule(selector, properties):
    for (key, val) in properties.items():
        if not isinstance(val, str):
            raise ValueError("non-string key", key)

    props_string = ";".join(("%s:%s" % (prop, value)) for (prop, value) in properties.items())
    return "%s{%s}" % (selector, props_string)

def dump_css(file, rules):
    file.write(AutogenHeader)

    for (selectors, properties) in rules.items():
        file.write("%s\n" % (format_rule(selectors, properties)))

def dump_js(file, map):
    file.write(AutogenHeader)
    file.write("var emote_map = {\n")

    strings = ["%r:%r" % (emote, css_class.lstrip(".")) for (emote, css_class) in map.items()]
    file.write(",\n".join(strings))

    file.write("\n}\n")

def main():
    parser = argparse.ArgumentParser(description="Generates BetterPonymotes's data files from a set of YAML inputs")
    parser.add_argument("--css", help="Output CSS file", default="emote-classes.css")
    parser.add_argument("--nsfw", help="Output NSFW CSS file", default="nsfw-emote-classes.css")
    parser.add_argument("--js", help="Output JS file", default="emote-map.js")
    parser.add_argument("yaml", help="Input YAML files", nargs="+")
    args = parser.parse_args()

    emotes = []

    print("Processing emotes")
    for filename in args.yaml:
        with open(filename) as file:
            emotes.extend(process_file(filename, yaml.load(file)))

    print("Building files")
    css_rules, nsfw_css_rules, js_map = build_data(emotes)

    print("Simplifying CSS")
    simplify(css_rules)
    simplify(nsfw_css_rules)

    print("Dumping")
    with open(args.css, "w") as css_out:
        dump_css(css_out, css_rules)
    with open(args.nsfw, "w") as nsfw_out:
        dump_css(nsfw_out, nsfw_css_rules)
    with open(args.js, "w") as js_out:
        dump_js(js_out, js_map)

if __name__ == "__main__":
    main()
