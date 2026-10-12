"""The office's tables for the structure (decisions 0008, 0040). None of the standards' values are
in the repository: each table names where the office finds them, and every result names the
edition it used."""

from uea.calc.data import Col, Spec
from uea.packs.arch.kinds import RoomUse

USES: tuple[str, ...] = RoomUse.__args__  # type: ignore[attr-defined]

UNIT_WEIGHT = Spec(
    "unit-weight",
    "Unit weights of building materials",
    "DIN EN 1991-1-1, Anhang A, or the manufacturer",
    (
        Col("material", "text", "material, as the layers name it"),
        Col("gamma", "num", "unit weight γ, kN/m³"),
    ),
    ("material",),
    "One row for each material the load-bearing walls, slabs, floors, partitions and roofs name."
    " A layer of rafters with insulation between them: the weight of both, smeared over the"
    " layer.",
)
IMPOSED = Spec(
    "imposed-load",
    "Imposed loads on floors by room use",
    "DIN EN 1991-1-1/NA, Tabelle 6.1DE",
    (
        Col("use", "text", "room use, as UEA names it", USES),
        Col("qk", "num", "imposed load q_k, kN/m²", sign="zero"),
    ),
    ("use",),
    "One row for each use the rooms of the project have.",
)
PARTITION = Spec(
    "partition-load",
    "Surcharge for light partitions",
    "DIN EN 1991-1-1, 6.3.1.2(8), with NA",
    (
        Col("upto", "num", "weight of the partition up to, kN/m"),
        Col("qk", "num", "surcharge on the imposed load, kN/m²"),
    ),
    ("upto",),
    "A partition heavier than the last row is a line load on its slab.",
)
FACTOR_NAMES = (
    "gamma-g",
    "gamma-q",
    "gamma-g-inf",
    "gamma-m",
    "zeta",
    "rho2",
    "gamma-c",
    "alpha-cc",
    "gamma-s",
    "fyk",
    "d1",
    "crdc",
    "vmin",
    "rho-min-ft",
    "rho-min",
)
FACTORS = Spec(
    "struct-factors",
    "Partial factors and design settings",
    "DIN EN 1990/NA, Tabelle NA.A.1.2(B); DIN EN 1996-1-1/NA, 2.4.3, 3.7.1; DIN EN 1996-3/NA,"
    " 4.2.2.3; DIN EN 1992-1-1/NA, 2.4.2.4, 3.1.6, 3.2",
    (
        Col("name", "text", "which value", FACTOR_NAMES),
        Col("value", "num", "its value"),
    ),
    ("name",),
    "gamma-g, gamma-q: γ_G and γ_Q; gamma-g-inf: γ_G of a favourable permanent action (the"
    " uplift of a roof); gamma-m: γ_M of the masonry; zeta: ζ for the long-term strength of"
    " masonry; rho2: ρ_2 of a wall held by slabs at both ends; gamma-c, alpha-cc: γ_C and α_cc"
    " of concrete; gamma-s: γ_S and fyk: f_yk (N/mm²) of the reinforcing steel; d1: the"
    " distance of the reinforcement's axis from the face of a slab, m; crdc: C_Rd,c and vmin:"
    " the factor of v_min = vmin · k^1.5 · √f_ck of a slab without shear reinforcement;"
    " rho-min-ft and rho-min: a_s,min = max(rho-min-ft · f_ctm / f_yk, rho-min) · b · d. Each"
    " calculation needs the rows it uses.",
)
LIMITS = Spec(
    "struct-limits",
    "Limits of the methods",
    "DIN EN 1996-3/NA, 4.2.1.1; DIN EN 1992-1-1/NA, 5.4(NA.5); DIN EN 1990/NA,"
    " A.1.4 with the office's choice of deflection limit",
    (
        Col(
            "name",
            "text",
            "which limit",
            ("building-height", "span", "qk", "clear-height", "xi", "deflection", "ld", "ld-span"),
        ),
        Col("value", "num", "its value"),
    ),
    ("name",),
    "building-height (m), span (the largest span of the slabs on a wall, m), qk (kN/m²) and"
    " clear-height (m): the conditions of the simplified method for masonry; xi: the largest"
    " x/d of a slab without a check of its rotation; deflection: n of the limit L/n of a beam"
    " or a rafter; ld and ld-span: the slenderness of a slab, l/d ≤ ld and ≤ ld-span / l (l in"
    " m).",
)
SNOW = Spec(
    "snow-shape",
    "Snow load shape coefficient μ1 of a roof by its pitch",
    "DIN EN 1991-1-3, 5.3.2 and Tabelle 5.2, with NA",
    (
        Col("pitch", "num", "roof pitch, °", sign="zero"),
        Col("mu1", "num", "shape coefficient μ1", sign="zero"),
    ),
    ("pitch",),
    "Rows from 0° up to the steepest pitch of the project; between rows UEA interpolates.",
)
WIND = Spec(
    "wind-roof",
    "External pressure coefficients of a roof by its pitch",
    "DIN EN 1991-1-4, 7.2.3 to 7.2.6, with NA",
    (
        Col("pitch", "num", "roof pitch, °", sign="zero"),
        Col("pressure", "num", "c_pe,10 for pressure on the roof (0 if none)", sign="zero"),
        Col("suction", "num", "c_pe,10 for suction, negative", sign="any"),
    ),
    ("pitch",),
    "The coefficients the office takes for the load of a roof plane on the walls under its"
    " eaves (its choice of zone, e.g. H); between rows UEA interpolates.",
)
PSI = Spec(
    "struct-psi",
    "Combination factors ψ0",
    "DIN EN 1990/NA, Tabelle NA.A.1.1",
    (
        Col("action", "text", "variable action", ("imposed", "snow", "wind")),
        Col("psi0", "num", "ψ0", sign="zero"),
    ),
    ("action",),
    "imposed: the imposed loads of the rooms (category A); snow at the site's altitude; wind.",
)
SECTION = Spec(
    "beam-section",
    "Sections of beams",
    "the manufacturer's tables or DIN EN 10365 (steel), DIN EN 14080 (glued laminated timber)",
    (
        Col("name", "text", "the section, as the beam names it"),
        Col("material", "text", "a material of the beam-material table"),
        Col("w", "num", "section modulus W_y, cm³"),
        Col("i", "num", "second moment of area I_y, cm⁴"),
        Col("av", "num", "shear area A_v, cm²"),
        Col("g", "num", "weight, kN/m"),
    ),
    ("name",),
    "One row for each section the beams name.",
)
BEAM_MATERIAL = Spec(
    "beam-material",
    "Strengths of the materials of beams",
    "DIN EN 1993-1-1/NA (steel), DIN EN 1995-1-1/NA and DIN EN 14080 (timber)",
    (
        Col("material", "text", "the material, as the beam-section table names it"),
        Col("fk", "num", "bending strength f_y or f_m,k, N/mm²"),
        Col("fvk", "num", "shear strength f_y/√3 or f_v,k, N/mm²"),
        Col("e", "num", "modulus of elasticity, N/mm²"),
        Col("gamma", "num", "partial factor γ_M"),
        Col("kmod", "num", "k_mod for the load duration of the design (1 for steel)"),
    ),
    ("material",),
    "f_d = k_mod · f_k / γ_M for bending and shear.",
)
MASONRY = Spec(
    "masonry",
    "Characteristic compressive strength of masonry",
    "DIN EN 1996-1-1/NA, NA.D, or the national technical approval of the unit",
    (
        Col("material", "text", "the material of a wall's core layer"),
        Col("fk", "num", "f_k of the unit with its mortar, N/mm²"),
    ),
    ("material",),
    "One row for each material the cores of the load-bearing walls name.",
)
MASONRY_END = Spec(
    "masonry-end",
    "Reduction factor Φ2 of a wall at the end support of a slab",
    "DIN EN 1996-3/NA, 4.2.2.3",
    (
        Col("upto", "num", "span of the slab l_f up to, m"),
        Col("phi", "num", "Φ2"),
    ),
    ("upto",),
    "For the strength class of the project's masonry; a span longer than the last row is"
    " outside the table.",
)
CONCRETE = Spec(
    "concrete",
    "Concrete of slabs",
    "DIN EN 1992-1-1, Tabelle 3.1, for the strength class the office specifies",
    (
        Col("material", "text", "the material of a slab's core layer"),
        Col("fck", "num", "f_ck, N/mm²"),
        Col("ecm", "num", "E_cm, N/mm²"),
    ),
    ("material",),
    "One row for each material the cores of the slabs name.",
)
LINTEL = Spec(
    "lintel",
    "Lintels over openings in load-bearing walls",
    "the manufacturer's load tables (allgemeine bauaufsichtliche Zulassung)",
    (
        Col("type", "text", "the lintel, for the report"),
        Col("t", "num", "the thickness of wall core it is for, m"),
        Col("span", "num", "clear span up to, m"),
        Col("qrd", "num", "design load it carries at that span, kN/m"),
    ),
    ("type", "t", "span"),
    "UEA takes, for each opening, the first type in the table's order that carries the load"
    " over the span in a wall of that thickness.",
)

TIMBER = Spec(
    "timber",
    "Strength classes of solid and glued laminated timber",
    "DIN EN 338, DIN EN 14080; DIN EN 1995-1-1 with NA (k_mod, γ_M, k_cr, β_c)",
    (
        Col("material", "text", "the strength class, as a rafter names it: C24, GL24h, ..."),
        Col("fmk", "num", "bending strength f_m,k, N/mm²"),
        Col("ft0k", "num", "tension strength along the grain f_t,0,k, N/mm²"),
        Col("fc0k", "num", "compression strength along the grain f_c,0,k, N/mm²"),
        Col("fvk", "num", "shear strength f_v,k, N/mm²"),
        Col("e0mean", "num", "mean modulus of elasticity E_0,mean, N/mm²"),
        Col("e005", "num", "5 % modulus of elasticity E_0,05, N/mm²"),
        Col("kmod", "num", "k_mod for the roof's load duration and service class"),
        Col("gamma", "num", "γ_M"),
        Col("kcr", "num", "k_cr for the shear of cracked members"),
        Col("betac", "num", "β_c, the straightness factor for buckling"),
    ),
    ("material",),
    "One row for each strength class the rafters and collar beams use.",
)
COLUMN_SECTION = Spec(
    "column-section",
    "Sections of columns",
    "the manufacturer's tables or DIN EN 10365 (steel); DIN EN 1993-1-1, 6.3.1 (buckling curves)",
    (
        Col("name", "text", "the section, as the column names it"),
        Col("material", "text", "a material of the beam-material table"),
        Col("a", "num", "area A, cm²"),
        Col("imin", "num", "the smaller second moment of area, cm⁴"),
        Col("alpha", "num", "imperfection factor α of its buckling curve about that axis"),
        Col("g", "num", "weight, kN/m"),
    ),
    ("name",),
    "One row for each section the columns use.",
)
WIND_WALL = Spec(
    "wind-wall",
    "External pressure coefficients of the walls",
    "DIN EN 1991-1-4, 7.2.2 and Tabelle 7.1, with NA",
    (
        Col("upto", "num", "h/d up to"),
        Col("d", "num", "c_pe,10 of zone D, the wall the wind blows on", sign="zero"),
        Col("e", "num", "c_pe,10 of zone E, the wall on the lee side, negative", sign="any"),
    ),
    ("upto",),
    "For the horizontal wind on the building (bracing): rows by h/d, the first that covers it.",
)
MASONRY_SHEAR = Spec(
    "masonry-shear",
    "Shear strength of masonry",
    "DIN EN 1996-1-1, 3.6.2, with NA",
    (
        Col("material", "text", "the core material of a wall, as its build-up names it"),
        Col("fvk0", "num", "initial shear strength f_vk0, N/mm²"),
        Col("fvlt", "num", "the limit of f_vk, N/mm²"),
    ),
    ("material",),
    "For the bracing walls: f_vk = min(f_vk0 + 0.4 · σ_d, f_vlt).",
)
