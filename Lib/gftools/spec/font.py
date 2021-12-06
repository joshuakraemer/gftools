"""
# Google Fonts Specification

This module generates our documentation, FB checks and fixes.

TODO Perhaps this spec module should be its own repo?
We could then import it into both gftools and fontbakery
discuss with team first before doing this.
"""
import re
from fontTools.misc.fixedTools import otRound
from fontTools.ttLib import TTFont, newTable, getTableModule
from fontTools.ttLib.tables import ttProgram
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
from fontTools.ttLib.tables._f_v_a_r import NamedInstance
from gftools.util.google_fonts import _KNOWN_WEIGHTS
from gftools.utils import (
    download_family_from_Google_Fonts,
    Google_Fonts_has_family,
    find_regular_styles,
    font_stylename,
    font_familyname,
    family_bounding_box,
    get_unencoded_glyphs,
    normalize_unicode_marks,
    partition_cmap,
    typo_metrics_enabled,
    validate_family,
    unique_name,
)
from gftools.axisreg import axis_registry
from gftools.util.styles import (get_stylename, is_regular, is_bold, is_italic)
from gftools.stat import gen_stat_tables

from os.path import basename, splitext
from copy import deepcopy
import logging
from glyphsLib import GSFont
from defcon import Font
from datetime import datetime


log = logging.getLogger(__name__)


# The _KNOWN_WEIGHT_VALUES constant is used internally by the GF Engineering
# team so we cannot update ourselves. TODO (Marc F) unify this one day
WEIGHT_NAMES = _KNOWN_WEIGHTS
del WEIGHT_NAMES[""]
WEIGHT_NAMES["Hairline"] = 1
WEIGHT_NAMES["ExtraBlack"] = 1000
WEIGHT_VALUES = {v: k for k, v in WEIGHT_NAMES.items()}




class BaseSpec:

    TITLE = ""
    TEXT = ""
    LINKS = []

    def __init__(self, font, siblings=[], license="ofl", repo=None):
        self.font = font
        self.siblings = siblings
        self.license = license
        self.format = self._get_format()
        self.family_name, self.style_name = self._get_family_name()
        self.repo = repo
        self.gf_family = self._get_gf_family()
        self.gf_regular = find_regular_styles(self.gf_family)
        self.gf_regular = None if not self.gf_regular else self.gf_regular[0]
    
    def _get_format(self):
        if isinstance(self.font, TTFont):
            return "sfnt"
        elif isinstance(self.font, GSFont):
            return "glyphs"
        elif isinstance(self.font, Font):
            return "ufo"
        else:
            raise NotImplementedError(f"Current font format isn't supported")
    
    def _get_gf_family(self):
        try:
            fonts = download_family_from_Google_Fonts(self.family_name)
            return [TTFont(f) for f in fonts]
        except:
            return None

    def fix_ttf(self):
        self.skip_msg()

    def fix_ufo(self):
        self.skip_msg()
    
    def fix_glyphs(self):
        self.skip_msg()

    def check_ttf(self):
        self.skip_msg()
        return True, ""

    def check_ufo(self):
        self.skip_msg()
        return True, ""

    def check_glyphs(self):
        self.skip_msg()
        return True, ""

    def skip_msg(self):
        log.info(f"Skipping {self.__class__} since a fix doesn't exist for {self.format}")
    
    def fix(self):
        if self.format == "sfnt":
            self.fix_ttf()
        elif self.format == "glyphs":
            self.fix_glyphs()
        elif self.format == "ufo":
            self.fix_ufo()
    
    def check(self):
        if self.format == "sfnt":
            return self.check_ttf()
        elif self.format == "glyphs":
            return self.check_glyphs()
        elif self.format == "ufo":
            return self.check_ufo()

    def _get_family_name(self):
        if self.format == "glyphs":
            return self.font.familyName, None
        elif self.format == "ufo":
            return self.font.info.familyName, self.font.info.styleName
        elif self.format == "sfnt":
            return font_familyname(self.font), font_stylename(self.font)


class SpecFSType(BaseSpec):
    TITLE = "FsType"
    TEXT = "Must be set to 0 (Installable embedding)"
    LINKS = ["https://docs.microsoft.com/en-us/typography/opentype/spec/os2#fstype"]

    def _check(self, current, expected):
        if current != expected:
            return False, f"OS/2.fsType is {current}. Expected {expected}."
        return True, "Font has correct OS/2.fsType"

    def check_ttf(self):
        fs_type = self.font['OS/2'].fsType
        return self._check(fs_type, 0)

    def check_ufo(self):
        fs_type = self.font.info.openTypeOS2Type
        return self._check(fs_type, [])

    def check_glyphs(self):
        fs_type = None if "fsType" not in self.font.customParameters else self.font.customParameters["fsType"]
        return self._check(fs_type, [])

    def fix_ttf(self):
        self.font['OS/2'].fsType = 0
    
    def fix_ufo(self):
        self.font.info.openTypeOS2Type = []
    
    def fix_glyphs(self):
        self.font.customParameters["fsType"] = []


class SpecStyles(BaseSpec):
    TITLE = "Supported Styles"
    TEXT = """
    Google’s static fonts API supports up to 18 styles in one family: up to 9 weights (Thin–Black), + their matching Italics. The table below lists each style’s specific name table and bit settings.

    `fontmake` doesn’t produce platform 1 (Mac) name entries any more. The respective columns below are for reference, but are optional.

    | Filename                        | Family Name (ID 1, Win) | Subfamily Name (ID 2, Win) | *optional:* Family Name (ID 1, Mac) | *optional:* Subfamily Name (ID 2, Mac) | Typographic Family Name (ID 16) | Typo Subfamily Name (ID 17) | OS/2 usWeightClass | OS/2 fsSelection | head macStyle |
    |---------------------------------|------------------------|---------------------------|------------------------|---------------------------|-------------------------------------|---------------------------------|--------------------|---------------------|----------------|
    | FamilyName-Thin.ttf             | Family Name Thin       | Regular                   | Family Name            | Thin                      | Family Name                         | Thin                            | 100                | bit 6               |                |
    | FamilyName-ExtraLight.ttf       | Family Name ExtraLight | Regular                   | Family Name            | ExtraLight                | Family Name                         | ExtraLight                      | 200                | bit 6               |                |
    | FamilyName-Light.ttf            | Family Name Light      | Regular                   | Family Name            | Light                     | Family Name                         | Light                           | 300                | bit 6               |                |
    | FamilyName-Regular.ttf          | Family Name            | Regular                   | Family Name            | Regular                   |                                     |                                 | 400                | bit 6               |                |
    | FamilyName-Medium.ttf           | Family Name Medium     | Regular                   | Family Name            | Medium                    | Family Name                         | Medium                          | 500                | bit 6               |                |
    | FamilyName-SemiBold.ttf         | Family Name SemiBold   | Regular                   | Family Name            | SemiBold                  | Family Name                         | SemiBold                        | 600                | bit 6               |                |
    | FamilyName-Bold.ttf             | Family Name            | Bold                      | Family Name            | Bold                      |                                     |                                 | 700                | bit 5               | bit 0          |
    | FamilyName-ExtraBold.ttf        | Family Name ExtraBold  | Regular                   | Family Name            | ExtraBold                 | Family Name                         | ExtraBold                       | 800                | bit 6               |                |
    | FamilyName-Black.ttf            | Family Name Black      | Regular                   | Family Name            | Black                     | Family Name                         | Black                           | 900                | bit 6               |                |
    |                                 |                        |                           |                        |                           |                                     |                                 |                    |                     |                |
    | FamilyName-ThinItalic.ttf       | Family Name Thin       | Italic                    | Family Name            | Thin Italic               | Family Name                         | Thin Italic                     | 100                | bit 0               | bit 1          |
    | FamilyName-ExtraLightItalic.ttf | Family Name ExtraLight | Italic                    | Family Name            | ExtraLight Italic         | Family Name                         | ExtraLight Italic               | 200                | bit 0               | bit 1          |
    | FamilyName-LightItalic.ttf      | Family Name Light      | Italic                    | Family Name            | Light Italic              | Family Name                         | Light Italic                    | 300                | bit 0               | bit 1          |
    | FamilyName-Italic.ttf           | Family Name            | Italic                    | Family Name            | Italic                    |                                     |                                 | 400                | bit 0               | bit 1          |
    | FamilyName-MediumItalic.ttf     | Family Name Medium     | Italic                    | Family Name            | Medium Italic             | Family Name                         | Medium Italic                   | 500                | bit 0               | bit 1          |
    | FamilyName-SemiBoldItalic.ttf   | Family Name SemiBold   | Italic                    | Family Name            | SemiBold Italic           | Family Name                         | SemiBold Italic                 | 600                | bit 0               | bit 1          |
    | FamilyName-BoldItalic.ttf       | Family Name            | Bold Italic               | Family Name            | Bold Italic               |                                     |                                 | 700                | bit 5 + bit 0       | bit 0 + bit 1  |
    | FamilyName-ExtraBoldItalic.ttf  | Family Name ExtraBold  | Italic                    | Family Name            | ExtraBold Italic          | Family Name                         | ExtraBold Italic                | 800                | bit 0               | bit 1          |
    | FamilyName-BlackItalic.ttf      | Family Name Black      | Italic                    | Family Name            | Black Italic              | Family Name                         | Black Italic                    | 900                | bit 0               | bit 1          |


    If a family has styles which are not in the above table, they should be released as a separate/new family. To do this, append any Unsupported style (e.g Condensed) to the family name, so it becomes part of the family name, rather than part of the style name. We frequently use this approach for [Condensed](https://fonts.google.com/?query=condensed) and [smallcap](https://fonts.google.com/?query=sc) sibling families.

    For projects which use glyphsapp, we have an example [repository](https://github.com/davelab6/glyphs-export) which contains glyphs files that are set correctly.
    """
    def fix_ttf(self):
        self.font["OS/2"].usWeightClass = self._expected_ttf_weightclass()
        self.font["OS/2"].fsSelection = self._expected_ttf_fs_selection()
        self.font["head"].macStyle = self._expected_ttf_mac_style()
    
    def check_ttf(self):
        fails = []
        current_weightclass = self.font["OS/2"].usWeightClass
        expected_weightclass = self._expected_ttf_weightclass()
        if current_weightclass != expected_weightclass:
            fails.append(f"OS/2.usWeightClass is {current_weightclass}. Expected {expected_weightclass}")
        
        current_fsselection = self.font["OS/2"].fsSelection
        expected_fsselection = self._expected_ttf_fs_selection()
        if current_fsselection != expected_fsselection:
            fails.append(f"OS/2.fsSelection is {current_fsselection}. Expected {expected_fsselection}")
        
        current_macstyle = self.font["head"].macStyle
        expected_macstyle = self._expected_ttf_mac_style()
        if current_macstyle != expected_macstyle:
            fails.append(f"head.macStyle is {current_macstyle}. Expected {expected_macstyle}")
        if not fails:
            return True, "Style linking bits are set correctly"
        return False, "\n".join(fails)
    
    def _expected_ttf_fs_selection(self):
        stylename = font_stylename(self.font)
        tokens = set(stylename.split())
        old_selection = fs_selection = self.font["OS/2"].fsSelection

        # turn off all bits except for bit 7 (USE_TYPO_METRICS)
        fs_selection &= 1 << 7

        if "Italic" in tokens:
            fs_selection |= 1 << 0
        if "Bold" in tokens:
            fs_selection |= 1 << 5
        # enable Regular bit for all other styles
        if not tokens & set(["Bold", "Italic"]):
            fs_selection |= 1 << 6
        return fs_selection

    def _expected_ttf_mac_style(self):
        stylename = font_stylename(self.font)
        tokens = set(stylename.split())
        mac_style = 0
        if "Italic" in tokens:
            mac_style |= 1 << 1
        if "Bold" in tokens:
            mac_style |= 1 << 0
        return mac_style

    def fix_glyphs(self):
        # fix instance names to pass gf spec
        for instance in self.font.instances:
            if 'Italic' in instance.name:
                instance.isItalic = True
                if instance.weight != 'Bold' and instance.weight != 'Regular':
                    instance.linkStyle = instance.weight
                else:
                    instance.linkStyle = ''
            else:
                instance.linkStyle = ''
        self._fix_glyphs_weightclass()
    
    def fix_ufo(self):
        # Can infer these values if we set the Style Map Family Name
        # and Style Map Style name correctly
        family_name = self.font.info.familyName
        style_name = self.font.info.styleName
        if style_name in set(["Regular", "Italic", "Bold", "Bold Italic"]):
            # delete any map names since they are not needed
            self.font.info.styleMapFamilyName = None
            self.font.info.styleMapStyleName = None
        else:
            family = f"{family_name} {style_name}".replace("Italic", "").strip()
            self.font.info.styleMapFamilyName = family
            style = "regular" if "Italic" not in style_name else "italic"
            self.font.info.styleMapStyleName = style
        self._fix_ufo_weightclass()

    def _expected_ttf_weightclass(self):
        stylename = font_stylename(self.font)
        tokens = stylename.split()
        return self._get_weight_class(tokens)
    
    def _fix_glyphs_weightclass(self):
        for instance in self.font.instances:
            tokens = instance.name.split()
            instance.weightClass = self._get_weight_class(tokens)
    
    def _fix_ufo_weightclass(self):
        tokens = self.font.info.styleName.split()
        self.font.info.openTypeOS2WeightClass = self._get_weight_class(tokens)
    
    def _get_weight_class(self, tokens):
        # Order WEIGHT_NAMES so longest names are first
        for style in sorted(WEIGHT_NAMES, key=lambda k: len(k), reverse=True):
            if style in tokens:
                return WEIGHT_NAMES[style]

        if "Italic" in tokens:
            return 400
        raise ValueError(
            f"Cannot determine usWeightClass because font style, '{stylename}' "
            f"doesn't have a weight token which is in our known "
            f"weights, '{WEIGHT_NAMES.keys()}'"
        )


class SpecNameTable(BaseSpec):
    OFL_LICENSE_URL = "http://scripts.sil.org/OFL"
    OFL_LICENSE = (
        "This Font Software is licensed under the SIL Open Font License, Version 1.1. "
        "This license is available with a FAQ at: https://scripts.sil.org/OFL"
    )

    def _expected_copyright(self):
        if self.license == "ofl":
            # TODO inherit old copyright date and possible RFN if it exists
            year = datetime.now().year
            rfn = None
            s = f"Copyright {year} The {self.family_name} Project Authors"
            if self.repo:
                s += f" ({self.repo})"
            if rfn:
                s += f". {rfn}"
            return s

    def check_glyphs(self):
        fails = []
        if self.license == "ofl":
            expected_copyright = self._expected_copyright()
            if self.font.copyright != expected_copyright:
                fails.append(f"Copyright should be {expected_copyright}")
            if "license" not in self.font.customParameters or \
                self.font.customParameters["license"] != self.OFL_LICENSE:
                fails.append(f"font license Custom Parameter should be {self.OFL_LICENSE}")
            if "licenseURL" not in self.font.customParameters or \
                self.font.customParameters["licenseURL"] != self.OFL_LICENSE_URL:
                fails.append(f"font licenseURL CustomParameter should be {self.OFL_LICENSE_URL}")
        if fails:
            return False, "\n".join(fails)

    def fix_glyphs(self):
        if self.license == "ofl":
            self.font.copyright = self._expected_copyright()
            self.font.customParameters["license"] = self.OFL_LICENSE
            self.font.custoParameters["licenseURL"] = self.OFL_LICENSE_URL


class SpecTables(BaseSpec):
    TITLE = "Unwanted Tables"

    UNWANTED_TABLES = frozenset(
        [
            "FFTM",
            "TTFA",
            "TSI0",
            "TSI1",
            "TSI2",
            "TSI3",
            "TSI5",
            "prop",
            "MVAR",
            "Debg",
        ]
    )

    def _expected_ttf_tables(self):
        tables = set(self.font.keys())
        return tables - SpecTables.UNWANTED_TABLES
    
    def check_ttf(self):
        current = set(self.font.keys())
        expected = self._expected_ttf_tables()
        unwanted = current - expected
        if unwanted:
            return False, f"Font contains redundant tables {unwanted}"
        return True, "Font has correct tables"

    def fix_ttf(self):
        current = set(self.font.keys())
        expected = self._expected_ttf_tables()
        redundant = current - expected
        for t in redundant:
            del self.font[t]


class SpecHinting(BaseSpec):
    TITLE = "Hinting"
    TEXT = \
    """
    ### Static Fonts:

    Static fonts should be hinted using the latest version of TTFAutohint. If the results look poor on Windows browsers, it's better to release the fonts unhinted with a GASP table set which is set to "grayscale / symmetric smoothing" (0x000A) across the full PPEM range. TTFAutohint often struggles to hint display or handwritten typefaces.

    ### VF Fonts:

    Variable Font hinting still doesn't have a clear policy. Marc Foley has been applying the following pattern:

    **Family already exists on Google Fonts as static fonts**

    If the family has over a billion weekly views, use VTT. Mike Duggan has documented how to VTT hint variable fonts, https://github.com/googlefonts/how-to-hint-variable-fonts.

    If the family has under a billion weekly views, release it unhinted with a smooth gasp table.
    """
    TTFA_FIRST_FUNC = [
        'PUSHB[ ]\t/* 1 value pushed */',
        '0',
        'FDEF[ ]\t/* FunctionDefinition */',
        'DUP[ ]\t/* DuplicateTopStack */',
        'PUSHB[ ]\t/* 1 value pushed */',
        '0',
        'NEQ[ ]\t/* NotEqual */',
        'IF[ ]\t/* If */',
        'RCVT[ ]\t/* ReadCVT */',
    ]
    SMOOTH_GASP = {0xFFFF: 15}
    VTT_GASP = {8: 10, 65535: 15}

    def fix_ttf(self):
        if "fpgm" not in self.font:
            self._fix_ttf_unhinted()
        elif self._is_ttfa_hinted():
            self._fix_ttfa_hinting()
        else:
            self._fix_vtt_hinting()
    
    def _is_ttfa_hinted(self):
        if "fpgm" not in self.font:
            return False
        return self.font['fpgm'].program.getAssembly()[:9] == self.TTFA_FIRST_FUNC

    def _fix_ttf_unhinted(self):
        program = ttProgram.Program()
        assembly = ["PUSHW[]", "511", "SCANCTRL[]", "PUSHB[]", "4", "SCANTYPE[]"]
        program.fromAssembly(assembly)
        prep = newTable("prep")
        prep.program = program
        self.font["prep"] = prep
        self._add_gasp_tbl(self.SMOOTH_GASP)
    
    def _add_gasp_tbl(self, gasp):
        gasp = newTable("gasp")
        # Set GASP so all sizes are smooth
        gasp.gaspRange = gasp
        self.font["gasp"] = gasp
    
    def _fix_ttfa_hinting(self):
        # We may want to throw in a custom gasp table here
        old = self.font["head"].flags
        self.font["head"].flags |= 1 << 3
        self._add_gasp_tbl(self.SMOOTH_GASP)
    
    def _fix_vtt_hinting(self):
        # TODO check if TSI tables are in font, if so, compile them
        self._add_gasp_tbl(self.VTT_GASP)

#    def fix_ufo(self):
#        # idk if there's hinting in ufo2ft yet
#        # this pr, https://github.com/googlefonts/ufo2ft/pull/335 was reverted
#        # dama just store their vtt instructions in the ufo's data dir
#        # let's just treat ufos as unhinted for the time being
#        self.font.info.openTypeGaspRangeRecords = [
#            {'rangeGaspBehavior': [0, 1, 2, 3], 'rangeMaxPPEM': 65535}
#        ]
#    
#    def fix_glyphs(self):
#        # Glyphsapp's gasp panel is broken
#        pass


class SpecInstances(BaseSpec):
    TITLE = "Variable Font Instances"
    TEXT = \
    """
    We are still revising how we name our instances and which particles we should/must include in instance names. At the moment (2020-06-30), Google Fonts only allows the following named instances:

    | | |
    |-|-|
    | Thin       | Thin Italic       |
    | ExtraLight | ExtraLight Italic |
    | Light      | Light Italic      |
    | Regular    | Italic            |
    | Medium     | Medium Italic     |
    | SemiBold   | SemiBold Italic   |
    | Bold       | Bold Italic       |
    | ExtraBold  | ExtraBold Italic  |
    | Black      | Black Italic      |


    We only allow weight and italic particles. If a font contains additional axes, they must not be mentioned in the instance names and the coordinates for each instance must be set to reasonable default e.g if your font contains a wdth axis, you don't want every instance's wdth coordinate value to be set to Condensed (75) you would set it to Normal (100).

    We have imposed this restriction for the following reasons:

    - Backwards compatibility with static fonts. Documents won't break if users swap static fonts for variable fonts.
    - We don't lock ourselves into an implementation we may want to change in the future. The specs are constantly evolving so it's best we wait for these to mature.
    - DTP applications do not properly support variable fonts yet. Variable font support is [experimental in Adobe applications](https://community.adobe.com/t5/indesign/variable-fonts-in-indesign/td-p/10718647).
    """
    def _expected_ttf_instances(self):
        if "fvar" not in self.font:
            return
        fvar = self.font["fvar"]
        default_axis_vals = {a.axisTag: a.defaultValue for a in fvar.axes}

        stylename = font_stylename(self.font)
        is_italic = "Italic" in stylename
        is_roman_and_italic = any(a for a in ("slnt", "ital") if a in default_axis_vals)

        wght_axis = next((a for a in fvar.axes if a.axisTag == "wght"), None)
        wght_min = int(wght_axis.minValue)
        wght_max = int(wght_axis.maxValue)

        nametable = self.font["name"]

        def gen_instances(is_italic):
            results = []
            for wght_val in range(wght_min, wght_max + 100, 100):
                name = (
                    WEIGHT_VALUES[wght_val]
                    if not is_italic
                    else f"{WEIGHT_VALUES[wght_val]} Italic".strip()
                )
                name = name.replace("Regular Italic", "Italic")

                coordinates = deepcopy(default_axis_vals)
                coordinates["wght"] = wght_val
                inst = {"subfamilyName": name, "coordinates": coordinates}
                results.append(inst)
            return results

        instances = []
        if is_roman_and_italic:
            for bool_ in (False, True):
                instances += gen_instances(is_italic=bool_)
        elif is_italic:
            instances += gen_instances(is_italic=True)
        else:
            instances += gen_instances(is_italic=False)
        return instances

    def check_ttf(self):
        if "fvar" not in self.font:
            return True, "Font is static. No instances to check"
        nametbl = self.font['name']
        current = [
            {
                "subfamilyName": nametbl.getName(i.subfamilyNameID, 3, 1, 0x409).toUnicode(),
                "coordinates": i.coordinates
            } for i in self.font['fvar'].instances]
        expected = self._expected_ttf_instances()
        if current != expected:
            return False, f"fvar Instances are {current}. Expected {expected}"
        return True, "fvar instances are correct"
    
    def fix_ttf(self):
        if "fvar" not in self.font:
            return
        expected = self._expected_ttf_instances()
        fvar = self.font["fvar"]
        nametable = self.font["name"]
        instances = []
        for i in expected:
            inst = NamedInstance()
            inst.subfamilyNameID = nametable.addName(i["subfamilyName"])
            inst.coordinates = i["coordinates"]
            instances.append(inst)
        fvar.instances = instances

    
    # TODO check_glyphs
    def fix_glyphs(self):
        # Strip out instances which are not Thin-Black or Thin Italic-Black Italic.
        # We cannot generate these from scratch because we cannot infer how designer units
        # will translate
        names = set(WEIGHT_VALUES.values())
        names |= set(f"{n} Italic".replace("Regular Italic", "Italic").strip() for n in names)
        self.font.instances = [i for i in self.font.instances if i.name in names] 
    
    def fix_designspace(self):
        # do the same as glyphsapp also update basefix to load designspaces
        pass


def update_nametable(ttFont, family_name=None, style_name=None):
    """Update a static font's name table. The updated name table will conform
    to the Google Fonts support styles table:
    https://github.com/googlefonts/gf-docs/tree/main/Spec#supported-styles

    If a style_name includes tokens other than wght and ital, these tokens
    will be appended to the family name e.g

    Input:
    family_name="MyFont"
    style_name="SemiCondensed SemiBold"

    Output:
    familyName (nameID 1) = "MyFont SemiCondensed SemiBold
    subFamilyName (nameID 2) = "Regular"
    typo familyName (nameID 16) = "MyFont SemiCondensed"
    typo subFamilyName (nameID 17) = "SemiBold"

    Google Fonts has used this model for several years e.g
    https://fonts.google.com/?query=cabin

    Args:
        ttFont:
        family_name: New family name
        style_name: New style name
    """
    if "fvar" in ttFont:
        raise ValueError("Cannot update the nametable for a variable font")
    nametable = ttFont["name"]

    # Remove nametable records which are not Win US English
    # TODO this is too greedy. We should preserve multilingual
    # names in the future. Please note, this has always been an issue.
    platforms = set()
    for rec in nametable.names:
        platforms.add((rec.platformID, rec.platEncID, rec.langID))
    platforms_to_remove = platforms ^ set([(3, 1, 0x409)])
    if platforms_to_remove:
        log.warning(
            f"Removing records which are not Win US English, {list(platforms_to_remove)}"
        )
        for platformID, platEncID, langID in platforms_to_remove:
            nametable.removeNames(
                platformID=platformID, platEncID=platEncID, langID=langID
            )

    # Remove any name records which contain linebreaks
    contains_linebreaks = []
    for r in nametable.names:
        for char in ("\n", "\r"):
            if char in r.toUnicode():
                contains_linebreaks.append(r.nameID)
    for nameID in contains_linebreaks:
        nametable.removeNames(nameID)

    if not family_name:
        family_name = font_familyname(ttFont)

    if not style_name:
        style_name = font_stylename(ttFont)

    ribbi = ("Regular", "Bold", "Italic", "Bold Italic")
    tokens = family_name.split() + style_name.split()

    nameids = {
        1: " ".join(t for t in tokens if t not in ribbi),
        2: " ".join(t for t in tokens if t in ribbi) or "Regular",
        16: " ".join(t for t in tokens if t not in list(WEIGHT_NAMES) + ['Italic']),
        17: " ".join(t for t in tokens if t in list(WEIGHT_NAMES) + ['Italic']) or "Regular"
    }
    # Remove typo name if they match since they're redundant
    if nameids[16] == nameids[1]:
        del nameids[16]
    if nameids[17] == nameids[2]:
        del nameids[17]

    family_name = nameids.get(16) or nameids.get(1)
    style_name = nameids.get(17) or nameids.get(2)

    # create NameIDs 3, 4, 6
    nameids[4] = f"{family_name} {style_name}"
    nameids[6] = f"{family_name.replace(' ', '')}-{style_name.replace(' ', '')}"
    nameids[3] = unique_name(ttFont, nameids)

    # Pass through all records and replace occurences of the old family name
    # with the new family name
    current_family_name = font_familyname(ttFont)
    for record in nametable.names:
        string = record.toUnicode()
        if current_family_name in string:
            nametable.setName(
                string.replace(current_family_name, family_name),
                record.nameID,
                record.platformID,
                record.platEncID,
                record.langID,
            )

    # Remove previous typographic names
    for nameID in (16, 17):
        nametable.removeNames(nameID=nameID)

    # Update nametable with new names
    for nameID, string in nameids.items():
        nametable.setName(string, nameID, 3, 1, 0x409)


def fix_nametable(ttFont):
    """Spec a static font's name table so it conforms to the Google Fonts
    supported styles table:
    https://github.com/googlefonts/gf-docs/tree/main/Spec#supported-styles

    Args:
        ttFont: a TTFont instance
    """
    if "fvar" in ttFont:
        from fontTools.varLib.instancer.names import updateNameTable
        dflt_axes = {a.axisTag: a.defaultValue for a in ttFont['fvar'].axes}
        updateNameTable(ttFont, dflt_axes)
        return
    family_name = font_familyname(ttFont)
    style_name = font_stylename(ttFont)
    update_nametable(ttFont, family_name, style_name)


def rename_font(font, new_name):
    nametable = font["name"]
    current_name = font_familyname(font)
    if not current_name:
        raise Exception(
            "Name table does not contain nameID 1 or nameID 16. "
            "This tool does not work on webfonts."
        )
    log.info("Updating font name records")
    for record in nametable.names:
        record_string = record.toUnicode()

        no_space = current_name.replace(" ", "")
        hyphenated = current_name.replace(" ", "-")
        if " " not in record_string:
            new_string = record_string.replace(no_space, new_name.replace(" ", ""))
        else:
            new_string = record_string.replace(current_name, new_name)

        if new_string is not record_string:
            record_info = (
                record.nameID,
                record.platformID,
                record.platEncID,
                record.langID
            )
            log.info(
                "Updating {}: '{}' to '{}'".format(
                    record_info,
                    record_string,
                    new_string,
                )
            )
            record.string = new_string


def fix_filename(ttFont):
    ext = splitext(ttFont.reader.file.name)[1]
    family_name = font_familyname(ttFont)
    style_name = font_stylename(ttFont)

    if "fvar" in ttFont:
        axes = ",".join([a.axisTag for a in ttFont['fvar'].axes])
        if "Italic" in style_name:
            return f"{family_name}-Italic[{axes}]{ext}".replace(" ", "")
        return f"{family_name}[{axes}]{ext}".replace(" ", "")
    return f"{family_name}-{style_name}{ext}".replace(" ", "")


class BaseRegressionSpec(BaseSpec):
    def __init__(self, font):
        super().__init__(font=font)
        self.on_googlefonts = Google_Fonts_has_family(self.family_name)
        if not self.on_googlefonts:
            log.warning(f"Family is not on Google Fonts")
            return
        gf_family = download_family_from_Google_Fonts(self.family_name)
        self.gf_ttFonts = [TTFont(f) for f in gf_family]
        self.gf_font = self.match_font()
        self.gf_regular_font = self.gf_regular_style()

    def match_font(self):
        for gf_ttFont in self.gf_ttFonts:
            gf_styles = self._styles_in_ttFont(gf_ttFont)

            if self.format == "sfnt":
                styles = self._styles_in_ttFont(self.font)
            elif self.format == "ufo":
                styles = set([self.font.info.styleName])
            elif self.format == "glyphs":
                styles = set(i.name for i in self.font.instances)
            
            matching = styles & gf_styles
            if matching:
                return gf_ttFont
        # TODO return Regular instead
        log.warning(f"{self.style_name} isn't on Google Fonts. Using Regular font instead")
        return self.gf_regular_style()

    def _styles_in_ttFont(self, ttFont):
        name_tbl = ttFont['name']
        if "fvar" in ttFont:
            res = set()
            for inst in ttFont['fvar'].instances:
                res.add(
                    name_tbl.getName(inst.subfamilyNameID, 3, 1, 0x409).toUnicode()
                )
            return res
        return set([font_stylename(ttFont)])
    
    def gf_regular_style(self):
        for gf_ttFont in self.gf_ttFonts:
            styles = self._style_in_ttFont(gf_ttFont)
            if "Regular" in styles:
                return gf_ttFont
        return self.gf_ttFonts[0]
 

class SpecInheritVerticalMetrics(BaseRegressionSpec):
    # TODO Adjust by upm vals
    
    def fix_ttf(self):
        self.font['OS/2'].usWinAscent = self.gf_font['OS/2'].usWinAscent
        self.font['OS/2'].usWinDescent = self.gf_font['OS/2'].usWinDescent
        self.font['OS/2'].sTypoAscender = self.gf_font['OS/2'].sTypoAscender
        self.font['OS/2'].sTypoDescender = self.gf_font['OS/2'].sTypoDescender
        self.font['OS/2'].sTypoLineGap = self.gf_font['OS/2'].sTypoLineGap
        self.font['hhea'].ascender = self.gf_font['hhea'].ascender
        self.font['hhea'].descender = self.gf_font['hhea'].descender
        self.font['hhea'].lineGap = self.gf_font['hhea'].lineGap
        if typo_metrics_enabled(self.gf_font):
            self.font["OS/2"].fsSelection |= 1 << 7
    
    def fix_ufo(self):
        self.font.info.openTypeOS2WinAscent = self.gf_font['OS/2'].usWinAscent
        self.font.info.openTypeOS2WinDescent = self.gf_font['OS/2'].usWinDescent
        self.font.info.openTypeOS2TypoAscender = self.gf_font['OS/2'].sTypoAscender
        self.font.info.openTypeOS2TypoDescender = self.gf_font['OS/2'].sTypoDescender
        self.font.info.openTypeOS2TypoLineGap = self.gf_font['OS/2'].sTypoLineGap
        self.font.info.openTypeHheaAscender = self.gf_font['hhea'].ascender
        self.font.info.openTypeHheaDescender = self.gf_font['hhea'].descender
        self.font.info.openTypeHheaLineGap = self.gf_font['hhea'].lineGap
        if typo_metrics_enabled(self.gf_font):
            if self.font.info.openTypeOS2Selection == None:
                self.font.info.openTypeOS2Selection = []
            if 7 not in self.font.info.openTypeOS2Selection:
                self.font.info.openTypeOS2Selection.append(7)
    
    def fix_glyphs(self):
        for master in self.font.masters:
            master.winAscent = self.gf_font['OS/2'].usWinAscent
            master.winDescent = self.gf_font['OS/2'].usWinDescent
            master.typoAscender = self.gf_font['OS/2'].sTypoAscender
            master.typoDescender = self.gf_font['OS/2'].sTypoDescender
            master.typoLineGap = self.gf_font['OS/2'].sTypoLineGap
            master.hheaAscender = self.gf_font["hhea"].ascender
            master.hheaDescender = self.gf_font['hhea'].descender
            master.hheaLineGap = self.gf_font['hhea'].lineGap
        for inst in self.font.instances:
            if typo_metrics_enabled(self.gf_font):
                inst.customParameters


class SpecDesignspace(BaseSpec):

    def fix_glyphs(self):
        """
        Check if designspace is orthogonal.
        """
        pass


class SpecVerticalMetrics(BaseSpec):
    """Spec a family's vertical metrics based on:
    https://github.com/googlefonts/gf-docs/tree/main/VerticalMetrics

    Args:
        ttFonts: a list of TTFont instances which belong to a family
    """
    
    def fix_ttf(self):
        src_font = self.gf_regular_font

        # TODO (Marc F) CJK Fonts?

        # If OS/2.fsSelection bit 7 isn't enabled, enable it and set the typo metrics
        # to the previous win metrics.
        if not typo_metrics_enabled(src_font):
            src_font["OS/2"].fsSelection |= 1 << 7  # enable USE_TYPO_METRICS
            src_font["OS/2"].sTypoAscender = src_font["OS/2"].usWinAscent
            src_font["OS/2"].sTypoDescender = -src_font["OS/2"].usWinDescent
            src_font["OS/2"].sTypoLineGap = 0

        # Set the hhea metrics so they are the same as the typo
        src_font["hhea"].ascent = src_font["OS/2"].sTypoAscender
        src_font["hhea"].descent = src_font["OS/2"].sTypoDescender
        src_font["hhea"].lineGap = src_font["OS/2"].sTypoLineGap

        # Set the win Ascent and win Descent to match the family's bounding box
        win_desc, win_asc = family_bounding_box(ttFonts)
        src_font["OS/2"].usWinAscent = win_asc
        src_font["OS/2"].usWinDescent = abs(win_desc)

        # Set all fonts vertical metrics so they match the src_font
        ttFont["OS/2"].fsSelection |= 1 << 7


class SpecItalicAngle(BaseSpec):
    # TODO (Marc F) implement for italic fonts
    def fix_ttf(self):
        style_name = font_stylename(self.font)
        if "Italic" not in style_name and self.font["post"].italicAngle != 0:
            self.font["post"].italicAngle = 0
    
    def fix_glyphs(self):
        for master in self.font.masters:
            if "Italic" not in master.name and master.italicAngle != 0:
                master.italicAngle = 0
    
    def fix_ufo(self):
        if "Italic" not in self.font.info.styleName and self.font.info.italicAngle != 0:
            self.font.info.italicAngle = 0


def fix_ascii_fontmetadata(font):
    """Speces TTF 'name' table strings to be ascii only"""
    for name in font['name'].names:
        title = name.string.decode(name.getEncoding())
        title = normalize_unicode_marks(title)
        name.string = title.encode(name.getEncoding())


def convert_cmap_subtables_to_v4(font):
  """Converts all cmap subtables to format 4.

  Returns a list of tuples (format, platformID, platEncID) of the tables
  which needed conversion."""
  cmap = font['cmap']
  outtables = []
  converted = []
  for table in cmap.tables:
    if table.format != 4:
      converted.append((table.format, table.platformID, table.platEncID))
    newtable = CmapSubtable.newSubtable(4)
    newtable.platformID = table.platformID
    newtable.platEncID = table.platEncID
    newtable.language = table.language
    newtable.cmap = table.cmap
    outtables.append(newtable)
  font['cmap'].tables = outtables
  return converted


def drop_nonpid0_cmap(font, report=True):
  keep, drop = partition_cmap(font, lambda table: table.platformID == 0, report)
  return drop


def drop_mac_cmap(font, report=True):
  keep, drop = partition_cmap(font, lambda table: table.platformID != 1 or table.platEncID != 0, report)
  return drop

def fix_pua(font):
    unencoded_glyphs = get_unencoded_glyphs(font)
    if not unencoded_glyphs:
        return

    ucs2cmap = None
    cmap = font["cmap"]

    # Check if an UCS-2 cmap exists
    for ucs2cmapid in ((3, 1), (0, 3), (3, 0)):
        ucs2cmap = cmap.getcmap(ucs2cmapid[0], ucs2cmapid[1])
        if ucs2cmap:
            break
    # Create UCS-4 cmap and copy the contents of UCS-2 cmap
    # unless UCS 4 cmap already exists
    ucs4cmap = cmap.getcmap(3, 10)
    if not ucs4cmap:
        cmapModule = getTableModule('cmap')
        ucs4cmap = cmapModule.cmap_format_12(12)
        ucs4cmap.platformID = 3
        ucs4cmap.platEncID = 10
        ucs4cmap.language = 0
        if ucs2cmap:
            ucs4cmap.cmap = deepcopy(ucs2cmap.cmap)
        cmap.tables.append(ucs4cmap)
    # Map all glyphs to UCS-4 cmap Supplementary PUA-A codepoints
    # by 0xF0000 + glyphID
    ucs4cmap = cmap.getcmap(3, 10)
    for glyphID, glyph in enumerate(font.getGlyphOrder()):
        if glyph in unencoded_glyphs:
            ucs4cmap.cmap[0xF0000 + glyphID] = glyph
    font['cmap'] = cmap
    return True


class SpecMonospace(BaseSpec):
    # TODO the implementation here isn't quite correct!
    TITLE = "Monospace Fonts"
    TEXT = \
    """
    We require the post table isSpecedPitch to be set, and the OS/2 panose
    table to have OS/2.panose.bProportion (bit 4) set correctly. If either
    of these is set incorrectly, users may get fallback glyphs which are
    not monospaced, if they type a character which doesn't exist in the font.
    """
    def fix_ttf(self):
        same_width = set()
        glyph_metrics = self.font['hmtx'].metrics
        for character in [chr(c) for c in range(65, 91)]:
            same_width.add(glyph_metrics[character][0])

        # enable Monospace properties
        if len(same_width) == 1:
            self.font['post'].isSpecedPitch = 1
            self.font['OS/2'].panose.bFamilyType = 2
            self.font['OS/2'].panose.bProportion = 9

        widths = [m[0] for m in self.font['hmtx'].metrics.values() if m[0] > 0]
        max_width = max(widths)
        self.font['hhea'].advanceWidthMax = max_width
        avg_width = int(sum(widths) / len(widths))
        self.font['OS/2'].xAvgCharWidth = avg_width
    
    def fix_ufo(self):
        same_width = set()
        for g in self.font:
            g_unicodes = set(g.unicodes)
            if g_unicodes.issubset(set(range(65, 91))):
                same_width.add(g.width)
        
        if len(same_width) == 1:
            self.font.info.postscriptIsSpecedPitch = True
            if not self.font.info.openTypeOS2Panose:
                self.font.info.openTypeOS2Panose = [0] * 10
            self.font.info.openTypeOS2Panose[0] = 2
            self.font.info.openTypeOS2Panose[3] = 9
        # hhea advanceWidthMax and OS/2 xAvgCharWidth will be calculated by fontmake
    
    def fix_glyphs(self):
        same_width = set()
        layer_ids = [m.id for m in self.font.masters]
        for glyph in self.font.glyphs:
            if not glyph.unicode:
                continue
            if int(glyph.unicode, 16) not in set(range(65, 91)):
                continue
            for l in glyph.layers:
                if l._layerId in layer_ids:
                    same_width.add(l.width)
        
        if len(same_width) == 1:
            self.font.customParameters["isSpecedPitch"] = True
            if not self.font.customParameters['panose']:
                self.font.customParameters['panose'] = [0] * 10
            self.font.customParameters['panose'][0] = 2
            self.font.customParameters['panose'][3] = 9
        # hhea advanceWidthMax and OS/2 xAvgCharWidth will be calculated by fontmake


def drop_superfluous_mac_names(ttfont):
    """Drop superfluous Mac nameIDs.

    The following nameIDS are kept:
    1: Font Family name,
    2: Font Family Subfamily name,
    3: Unique font identifier,
    4: Full font name,
    5: Version string,
    6: Postscript name,
    16: Typographic family name,
    17: Typographic Subfamily name
    18: Compatible full (Macintosh only),
    20: PostScript CID,
    21: WWS Family Name,
    22: WWS Subfamily Name,
    25: Variations PostScript Name Prefix.

    We keep these IDs in order for certain application to still function
    such as Word 2011. IDs 1-6 are very common, > 16 are edge cases.

    https://www.microsoft.com/typography/otspec/name.htm"""
    keep_ids = [1, 2, 3, 4, 5, 6, 16, 17, 18, 20, 21, 22, 25]
    changed = False
    for n in range(255):
        if n not in keep_ids:
            name = ttfont['name'].getName(n, 1, 0, 0)
            if name:
                changed = True
                ttfont['name'].names.remove(name)
    return changed


def drop_mac_names(ttfont):
    """Drop all mac names"""
    changed = False
    for n in range(255):
        name = ttfont['name'].getName(n, 1, 0, 0)
        if name:
            ttfont['name'].names.remove(name)
            changed = True
    return changed
