"""SQLAlchemy data models for UpliftRwanda (NISR 2026 Big Data Hackathon).

Schema layout (mirrors the API contract used by the React dashboard):

    regions          one row per Rwandan district (30 total)
    indicators       canonical catalog of FinScope 2024 / EICV7 indicators
    survey_metrics   long/tidy fact table: one observation per
                     (district x indicator x survey year)

All column types are kept cross-database (works on PostgreSQL AND SQLite) so the
seed script can be rehearsed locally against SQLite before hitting PostgreSQL.
"""

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def as_int(value):
    """Coerce driver/database values to int, tolerating Decimal/None/strings."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_float(value):
    """Coerce driver/database values to float, tolerating Decimal/None/strings."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class Base(DeclarativeBase):
    pass


class Region(Base):
    """A Rwandan district (province + area classification)."""

    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    province: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    district: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    area_type: Mapped[str] = mapped_column(String(16), nullable=False, default="rural")
    population_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    metrics: Mapped[list["SurveyMetric"]] = relationship(
        back_populates="region", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Region {self.district} ({self.province})>"


class Indicator(Base):
    """Canonical FinScope 2024 / EICV7 indicator definition."""

    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    indicator_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    indicator_name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(24), nullable=False, default="%")
    description: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    metrics: Mapped[list["SurveyMetric"]] = relationship(
        back_populates="indicator", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Indicator {self.indicator_code}>"


class SurveyMetric(Base):
    """One observed value for (district, indicator, survey year)."""

    __tablename__ = "survey_metrics"
    __table_args__ = (
        UniqueConstraint(
            "region_id",
            "indicator_id",
            "survey_year",
            name="uq_metric_region_indicator_year",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    indicator_id: Mapped[int] = mapped_column(
        ForeignKey("indicators.id", ondelete="CASCADE"), nullable=False, index=True
    )
    survey_year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    region: Mapped[Region] = relationship(back_populates="metrics")
    indicator: Mapped[Indicator] = relationship(back_populates="metrics")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<SurveyMetric region={self.region_id} indicator={self.indicator_id} year={self.survey_year} value={self.value}>"


class NationalTarget(Base):
    """Ministerial baseline target / rule-threshold override (JWT-managed).

    Keyed rows in this table override the engine's shipped official policy
    defaults (policy.py). Absence of a row means "use official default", so the
    seeder dropping the table during a reseed is always safe.
    """

    __tablename__ = "national_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False, default="official-default")
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default="")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<NationalTarget {self.target_key}={self.value} by {self.updated_by}>"


class DistrictCfsvaMetrics(Base):
    """CFSVA 2024 food-security & nutrition layer (separate from FinScope).

    NON-DESTRUCTIVE integration: a new table keyed on the SAME `regions.id`
    values; no existing table/column is altered. One row per district per
    survey wave (unique together on region + year).
    """

    __tablename__ = "district_cfsva_metrics"
    __table_args__ = (
        UniqueConstraint("region_id", "survey_year", name="uq_cfsva_region_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    survey_year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Food security & consumption (WFP/IPC scale)
    fies_moderate_severe_pct: Mapped[float] = mapped_column(Float, nullable=False)   # moderate+severe food insecurity, %
    fies_severe_pct: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)  # severely food insecure, %
    food_consumption_score: Mapped[float] = mapped_column(Float, nullable=False)    # mean FCS, 0-112 pts
    fcs_poor_pct: Mapped[float] = mapped_column(Float, nullable=False)             # share with poor FCS, %
    # Dietary diversity
    hdds: Mapped[float] = mapped_column(Float, nullable=False)                     # mean HDDS, 0-12
    # Malnutrition (children under 5)
    stunting_pct: Mapped[float] = mapped_column(Float, nullable=False)
    wasting_pct: Mapped[float] = mapped_column(Float, nullable=False)
    # Agricultural vulnerability / stress
    rcsi: Mapped[float] = mapped_column(Float, nullable=False)                     # reduced coping strategies index
    harvest_loss_pct: Mapped[float] = mapped_column(Float, nullable=False)         # hh with >=1 harvest loss, %

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<DistrictCfsvaMetrics region={self.region_id} year={self.survey_year}>"


class DistrictRdhsMetrics(Base):
    """RDHS 2025 living-standards & poverty-dynamics layer (separate from CFSVA).

    NON-DESTRUCTIVE integration, same pattern as DistrictCfsvaMetrics: a new
    table keyed on the SAME `regions.id` values; no existing table/column is
    altered. One row per district (unique on region + year), populated from
    `db/rdhs/rdhs_2025_district_panel.json` by seed_rdhs.py. All metric columns
    are nullable — microdata sparsity (e.g. tiny anthropometry samples) is
    preserved as NULL, never as a fake zero.
    """

    __tablename__ = "district_rdhs_metrics"
    __table_args__ = (
        UniqueConstraint("region_id", "survey_year", name="uq_rdhs_region_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    survey_year: Mapped[int] = mapped_column(Integer, nullable=False)

    households: Mapped[int] = mapped_column(Integer, nullable=False)
    births: Mapped[int] = mapped_column(Integer, nullable=False)
    children_measured: Mapped[int] = mapped_column(Integer, nullable=False)

    # Household living standards & financial inclusion (weighted shares)
    electricity_pct: Mapped[float] = mapped_column(Float, nullable=True)
    improved_water_pct: Mapped[float] = mapped_column(Float, nullable=True)
    improved_sanitation_pct: Mapped[float] = mapped_column(Float, nullable=True)
    bank_account_pct: Mapped[float] = mapped_column(Float, nullable=True)
    mobile_fintech_pct: Mapped[float] = mapped_column(Float, nullable=True)
    mobile_phone_pct: Mapped[float] = mapped_column(Float, nullable=True)
    insurance_pct: Mapped[float] = mapped_column(Float, nullable=True)
    urban_pct: Mapped[float] = mapped_column(Float, nullable=True)

    # Wealth distribution (quintile shares of hv270 + derived inequality cuts)
    wealth_q1: Mapped[float] = mapped_column(Float, nullable=True)
    wealth_q2: Mapped[float] = mapped_column(Float, nullable=True)
    wealth_q3: Mapped[float] = mapped_column(Float, nullable=True)
    wealth_q4: Mapped[float] = mapped_column(Float, nullable=True)
    wealth_q5: Mapped[float] = mapped_column(Float, nullable=True)
    wealth_p20_pct: Mapped[float] = mapped_column(Float, nullable=True)     # poorest-quintile share
    wealth_p40_pct: Mapped[float] = mapped_column(Float, nullable=True)     # bottom-40% share
    wealth_p60p_pct: Mapped[float] = mapped_column(Float, nullable=True)    # top-60% share

    # Birth-history mortality (per 1,000 live births, complete-exposure cohort)
    imr_per_1000: Mapped[float] = mapped_column(Float, nullable=True)
    u5mr_per_1000: Mapped[float] = mapped_column(Float, nullable=True)

    # Child anthropometry (BR children <60 months, WHO z-scores <-2 SD)
    stunting_pct: Mapped[float] = mapped_column(Float, nullable=True)
    underweight_pct: Mapped[float] = mapped_column(Float, nullable=True)
    wasting_pct: Mapped[float] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<DistrictRdhsMetrics region={self.region_id} year={self.survey_year}>"


class DistrictLfsMetrics(Base):
    """LFS 2025 labour-market layer (wide panel) — NON-DESTRUCTIVE integration.

    Same additive pattern as CFSVA/RDHS: a new table keyed on the SAME
    `regions.id` values; no existing table/column is altered. One row per
    district per survey year (unique on region + year), populated by
    seed_lfs.py and calibrated so population-weighted national means land on
    the official RLFS 2025 anchors (unemployment 12.4%, youth NEET 24.5%,
    LFPR gender gap 14.3 pp).

    Headline columns cover the district aggregates; male/female and education
    (General vs TVET) and disability splits let the dashboard honour gender /
    education / disability filters without a self-join.
    """

    __tablename__ = "district_lfs_metrics"
    __table_args__ = (
        UniqueConstraint("region_id", "survey_year", name="uq_lfs_region_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    survey_year: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- headline (all working-age population unless noted) ---
    unemployment_rate: Mapped[float] = mapped_column(Float, nullable=False)          # official anchor 12.4
    employment_ratio: Mapped[float] = mapped_column(Float, nullable=False)           # employed / working-age
    labor_underutilization_rate: Mapped[float] = mapped_column(Float, nullable=False)  # LU3 composite
    lfpr: Mapped[float] = mapped_column(Float, nullable=False)                       # participation 16+
    inactivity_rate: Mapped[float] = mapped_column(Float, nullable=False)            # out-of-labour-force share
    youth_unemployment_rate: Mapped[float] = mapped_column(Float, nullable=False)    # 16-30 labour force (CSV baseline)
    youth_neet_rate: Mapped[float] = mapped_column(Float, nullable=False)            # 16-30: not in employment, education or training (anchor 24.5)
    informal_employment_rate: Mapped[float] = mapped_column(Float, nullable=False)   # informal share of employment
    time_underemployment_rate: Mapped[float] = mapped_column(Float, nullable=False)  # time-related underemployment

    # --- gender split: male minus female LFPR gap (anchor 14.3 pp) ---
    lfpr_male: Mapped[float] = mapped_column(Float, nullable=False)
    lfpr_female: Mapped[float] = mapped_column(Float, nullable=False)
    unemployment_rate_male: Mapped[float] = mapped_column(Float, nullable=False)
    unemployment_rate_female: Mapped[float] = mapped_column(Float, nullable=False)
    youth_neet_male: Mapped[float] = mapped_column(Float, nullable=True)
    youth_neet_female: Mapped[float] = mapped_column(Float, nullable=True)

    # --- education outcome split: TVET graduates vs general-stream leavers ---
    tvet_unemployment_rate: Mapped[float] = mapped_column(Float, nullable=False)
    general_education_unemployment_rate: Mapped[float] = mapped_column(Float, nullable=False)

    # --- disability-status split ---
    disability_lfpr: Mapped[float] = mapped_column(Float, nullable=False)
    disability_unemployment_rate: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<DistrictLfsMetrics region={self.region_id} year={self.survey_year}>"


class DistrictLfsSegment(Base):
    """LFS 2025 disaggregation (long/tidy): demand-side filters.

    One row per (district, year, dimension, segment, indicator). Dimensions:
      gender     -> female | male
      education  -> primary | secondary_general | tvet | tertiary
      disability -> with_disability | without_disability
    Indicators (values in %):
      unemployment | lfpr | employment_ratio (+ neet for gender segments)
    """

    __tablename__ = "district_lfs_segments"
    __table_args__ = (
        UniqueConstraint(
            "region_id", "survey_year", "dimension", "segment", "indicator",
            name="uq_lfs_segment_row",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    survey_year: Mapped[int] = mapped_column(Integer, nullable=False)
    dimension: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    segment: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    indicator: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<DistrictLfsSegment {self.dimension}/{self.segment}/{self.indicator}={self.value}>"


class DistrictVupMetrics(Base):
    """VUP (Vision Umurenge Programme) beneficiary & operations layer.

    NON-DESTRUCTIVE additive table keyed on the SAME `regions.id`. One row per
    district per survey year (EICV7 VUP 2025 module + programme MIS vintage),
    populated by seed_vup.py.

    Columns carry the five VUP components as DIRECT beneficiary headcounts
    (Direct Support, Classic Public Works, Expanded Public Works,
    Nutrition-Sensitive Direct Support, Financial Services), the poverty
    profile among beneficiaries (official EICV7 VUP anchor: 41% overall
    poverty), and operational-efficiency shares (payment timeliness, digital
    disbursement channels — Umurenge SACCO / mobile money / cash).
    """

    __tablename__ = "district_vup_metrics"
    __table_args__ = (
        UniqueConstraint("region_id", "survey_year", name="uq_vup_region_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    survey_year: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- component caseloads (annual beneficiaries, headcount) ---
    beneficiaries_ds: Mapped[int] = mapped_column(Integer, nullable=False)    # Direct Support
    beneficiaries_cpw: Mapped[int] = mapped_column(Integer, nullable=False)   # Classic Public Works
    beneficiaries_epw: Mapped[int] = mapped_column(Integer, nullable=False)   # Expanded Public Works
    beneficiaries_nsds: Mapped[int] = mapped_column(Integer, nullable=False)  # Nutrition-Sensitive Direct Support
    beneficiaries_fs: Mapped[int] = mapped_column(Integer, nullable=False)    # Financial Services

    # --- poverty profile among VUP beneficiaries (official anchor: 41%) ---
    poverty_rate_among_beneficiaries: Mapped[float] = mapped_column(Float, nullable=False)
    extreme_among_beneficiaries: Mapped[float] = mapped_column(Float, nullable=False)  # extreme poor share (moderate = rate - extreme)

    # --- operational efficiency (programme-side, modelled) ---
    payment_timeliness_pct: Mapped[float] = mapped_column(Float, nullable=False)  # paid within the statutory window
    sacco_disbursement_pct: Mapped[float] = mapped_column(Float, nullable=False)  # Umurenge SACCO channel share
    momo_disbursement_pct: Mapped[float] = mapped_column(Float, nullable=False)   # Mobile Money channel share
    cash_disbursement_pct: Mapped[float] = mapped_column(Float, nullable=False)   # cash-in-transit share (sacco+momo+cash = 100)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<DistrictVupMetrics region={self.region_id} year={self.survey_year}>"
