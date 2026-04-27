import math
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="WDI Sustainability Dashboard",
    page_icon="🌍",
    layout="wide"
)

PALETTE = [
    "#00BFFF", "#E8A838", "#E91E8C", "#D95F4B",
    "#9B59B6", "#1ABC9C", "#E67E22", "#A8D8A8",
    "#F39C12", "#5B9BD5"
]

@st.cache_data
def load_data():
    df = pd.read_csv("data/wdi_clean.csv")
    return df

df = load_data()

all_countries_sorted = sorted(df["country"].unique().tolist())

# Sidebar
st.sidebar.title("🌍 WDI Dashboard")
st.sidebar.markdown(
    "Explore exchange rate volatility and sustainable development indicators across the world."
)
st.sidebar.divider()
st.sidebar.header("Filters")

selected_countries = st.sidebar.multiselect(
    "Select Countries",
    options=all_countries_sorted,
    default=["Spain", "United Kingdom", "India", "Japan"]
)

year_min = int(df["year"].min())
year_max = int(df["year"].max())
selected_years = st.sidebar.slider(
    "Year Range",
    min_value=year_min,
    max_value=year_max,
    value=(2000, 2024)
)

st.sidebar.divider()
st.sidebar.caption("Data: World Bank WDI v128, April 2026")

# Guard: empty selection
if not selected_countries:
    st.warning("Please select at least one country from the sidebar to view the charts.")
    st.stop()

# Filter data
filtered = df[
    (df["country"].isin(selected_countries)) &
    (df["year"] >= selected_years[0]) &
    (df["year"] <= selected_years[1])
].copy()

latest_year = df[df["year"] <= selected_years[1]]["year"].max()
latest_slice = df[df["year"] == latest_year]

# Assign colours by position in the current selection so no two countries share a colour.
# Stable within a session: adding a new country appends a new colour without shifting others.
selected_colour_map = {
    country: PALETTE[i % len(PALETTE)]
    for i, country in enumerate(selected_countries)
}

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Trends", "Compare", "About"])


# Overview tab
with tab1:
    st.header("Global Overview")
    st.caption(
        f"KPI cards reflect the current filter selection. "
        f"Choropleth shows global data for {latest_year}."
    )

    avg_fx  = filtered["exchange_rate"].mean()
    avg_gdp = filtered["gdp_per_capita"].mean()
    avg_pov = filtered["poverty_headcount"].mean()

    k1, k2, k3 = st.columns(3)
    k1.metric(
        label="Avg Exchange Rate (LCU per US$)",
        value=f"{avg_fx:,.1f}" if pd.notna(avg_fx) else "N/A"
    )
    k2.metric(
        label="Avg GDP per Capita (US$)",
        value=f"${avg_gdp:,.0f}" if pd.notna(avg_gdp) else "N/A"
    )
    k3.metric(
        label="Avg Poverty Headcount (%)",
        value=f"{avg_pov:.1f}%" if pd.notna(avg_pov) else "N/A"
    )

    st.divider()

    st.subheader(f"Official Exchange Rate by Country ({latest_year})")
    st.markdown(
        f"This map shows how many units of local currency each country needed to buy one US dollar "
        f"in {latest_year}. The scale is anchored at 1 LCU per US$ (off-white), with orange and "
        f"red indicating progressively weaker currencies. The US itself always appears off-white "
        f"as the reference currency. Dark grey countries have no data for this year."
    )
    st.caption(
        "Scale is log-transformed. Green indicates currencies at or below 1 LCU per US$ "
        "(e.g. Euro, Swiss franc, pound sterling). Off-white marks exact parity. "
        "Orange and red indicate progressively weaker currencies up to 500+ LCU. "
        "Hover any country for its exact value."
    )

    # Log-transform the exchange rate so that 1 LCU per US$ (log10 = 0) is the exact
    # midpoint of the colour scale. Below 1 graduates green; above 1 graduates red.
    map_df = latest_slice.dropna(subset=["exchange_rate"]).copy()
    # Clip lower bound at 0.5 LCU; no real-world currency in the dataset goes below that.
    # This gives the green side (0.5–1.0 LCU) a full third of the colour scale,
    # so Euro (~0.9) and pound (~0.8) countries land in a clearly visible green band
    # rather than a thin sliver near the off-white midpoint.
    map_df["log_fx"] = map_df["exchange_rate"].clip(lower=0.5, upper=500).apply(lambda x: math.log10(x))

    log_min = math.log10(0.5)  # -0.301, deepest green (strongest realistic currency)
    log_mid = 0.0               #  0.000, neutral off-white at exactly 1 LCU per US$
    log_max = math.log10(500)   #  2.699, deepest red (weakest currency shown)

    mid_pos = (log_mid - log_min) / (log_max - log_min)
    # mid_pos ≈ 0.10, so green spans the first 10% of the raw range.
    # We allocate colour stops generously within that 10% so the gradient is visible.

    custom_scale = [
        [0.0,                              "#005000"],  # deep green at 0.5 LCU
        [mid_pos * 0.35,                   "#2E8B57"],  # mid green (~0.65 LCU)
        [mid_pos * 0.70,                   "#7DC47D"],  # light green (~0.85 LCU)
        [mid_pos * 0.90,                   "#B8DDB8"],  # very light green (~0.93 LCU)
        [mid_pos,                          "#E8E0D0"],  # off-white at exactly 1 LCU
        [mid_pos + (1 - mid_pos) * 0.25,   "#E8A040"],  # light amber (~3 LCU)
        [mid_pos + (1 - mid_pos) * 0.50,   "#E8620C"],  # amber-orange (~10 LCU)
        [mid_pos + (1 - mid_pos) * 0.75,   "#C0300B"],  # deep red (~60 LCU)
        [1.0,                              "#5C0000"],  # darkest red at 500 LCU
    ]

    # Colour bar ticks in original LCU values
    tick_log_vals = [math.log10(0.5), math.log10(0.8), 0, 1, 2, math.log10(500)]
    tick_labels   = ["0.5", "0.8", "1 (neutral)", "10", "100", "500+"]

    # showland=True on the geo projection acts as a true base layer, painting every
    # territory grey before any choropleth trace is drawn. This catches disputed regions,
    # dependencies, and territories not in the dataset without needing an explicit list.
    fig_map = go.Figure()

    # Main data layer: countries with exchange rate data
    fig_map.add_trace(go.Choropleth(
        locations=map_df["iso3"],
        z=map_df["log_fx"],
        text=map_df["country"],
        customdata=map_df["exchange_rate"],
        colorscale=custom_scale,
        zmin=log_min,
        zmax=log_max,
        hovertemplate="%{text}<br>Exchange rate: %{customdata:.2f} LCU per US$<extra></extra>",
        marker_line_color="#2a3a4a",
        marker_line_width=0.5,
        colorbar=dict(
            title="LCU per US$",
            tickvals=tick_log_vals,
            ticktext=tick_labels,
        )
    ))

    fig_map.update_layout(
        geo=dict(
            showframe=False,
            showcoastlines=False,
            showocean=True,
            oceancolor="#1a2a3a",
            showlakes=True,
            lakecolor="#1a2a3a",
            showland=True,
            landcolor="#3a3a3a",
            bgcolor="rgba(0,0,0,0)",
            resolution=50,
            lataxis_range=[-60, 90],
        ),
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig_map, use_container_width=True)

    st.divider()

    # Cross-country bubble chart: thesis visualisation
    bubble_filter = st.toggle(
        "Show selected countries only",
        value=False,
        help="When on, the bubble chart shows only the countries chosen in the sidebar filter."
    )
    year_label = f"{selected_years[0]}–2024 Average" if selected_years[1] == year_max else f"{selected_years[0]}–{selected_years[1]} Average"
    bubble_title = (
        f"Exchange Rate vs Poverty: Selected Countries ({year_label})"
        if bubble_filter else
        f"Exchange Rate vs Poverty: All Countries ({year_label})"
    )
    st.subheader(bubble_title)
    if bubble_filter:
        st.markdown(
            "Each bubble represents one of your selected countries, plotted by its average exchange "
            "rate against its average poverty headcount over the selected year range. Bubble size "
            "reflects average GDP per capita and colour matches the country colour used across all "
            "other charts in this dashboard."
        )
        st.caption(
            "Bubble size = average GDP per capita. Colour = country (matches sidebar selection). "
            "X-axis capped at 1,500 LCU for readability. "
            "Countries with no poverty survey data are excluded entirely."
        )
    else:
        st.markdown(
            f"Each bubble represents one country, plotted by its average exchange rate against its "
            f"average poverty headcount over the {year_label}. Bubble size reflects average GDP "
            f"per capita and colour indicates region. The large cluster of wealthy, low-poverty "
            f"countries sits near the left; these are high-income economies with currencies close "
            f"to dollar parity. Moving right, exchange rates rise and poverty tends to follow."
        )
        st.caption(
            "Bubble size = average GDP per capita. Colour = world region. "
            "X-axis capped at 1,500 LCU for readability; a small number of extreme outliers "
            "(e.g. historical Zimbabwe rates) are excluded from the visual but included in hover values. "
            "Countries with no poverty survey data are excluded entirely."
        )

    # ISO3-to-region mapping for bubble colour encoding
    REGION_MAP = {
        "DZA":"Africa","AGO":"Africa","BEN":"Africa","BWA":"Africa","BFA":"Africa",
        "BDI":"Africa","CPV":"Africa","CMR":"Africa","CAF":"Africa","TCD":"Africa",
        "COM":"Africa","COD":"Africa","COG":"Africa","CIV":"Africa","DJI":"Africa",
        "EGY":"Africa","GNQ":"Africa","ERI":"Africa","SWZ":"Africa","ETH":"Africa",
        "GAB":"Africa","GMB":"Africa","GHA":"Africa","GIN":"Africa","GNB":"Africa",
        "KEN":"Africa","LSO":"Africa","LBR":"Africa","LBY":"Africa","MDG":"Africa",
        "MWI":"Africa","MLI":"Africa","MRT":"Africa","MUS":"Africa","MAR":"Africa",
        "MOZ":"Africa","NAM":"Africa","NER":"Africa","NGA":"Africa","RWA":"Africa",
        "STP":"Africa","SEN":"Africa","SLE":"Africa","SOM":"Africa","ZAF":"Africa",
        "SSD":"Africa","SDN":"Africa","TZA":"Africa","TGO":"Africa","TUN":"Africa",
        "UGA":"Africa","ZMB":"Africa","ZWE":"Africa","ESH":"Africa","SYC":"Africa",
        "AFG":"Asia","ARM":"Asia","AZE":"Asia","BHR":"Asia","BGD":"Asia",
        "BTN":"Asia","BRN":"Asia","KHM":"Asia","CHN":"Asia","GEO":"Asia",
        "IND":"Asia","IDN":"Asia","IRN":"Asia","IRQ":"Asia","ISR":"Asia",
        "JPN":"Asia","JOR":"Asia","KAZ":"Asia","KWT":"Asia","KGZ":"Asia",
        "LAO":"Asia","LBN":"Asia","MYS":"Asia","MDV":"Asia","MNG":"Asia",
        "MMR":"Asia","NPL":"Asia","PRK":"Asia","OMN":"Asia","PAK":"Asia",
        "PHL":"Asia","QAT":"Asia","SAU":"Asia","SGP":"Asia","KOR":"Asia",
        "LKA":"Asia","SYR":"Asia","TWN":"Asia","TJK":"Asia","THA":"Asia",
        "TLS":"Asia","TKM":"Asia","ARE":"Asia","UZB":"Asia","VNM":"Asia",
        "YEM":"Asia","PSE":"Asia","MAC":"Asia","HKG":"Asia",
        "ALB":"Europe","AND":"Europe","AUT":"Europe","BLR":"Europe","BEL":"Europe",
        "BIH":"Europe","BGR":"Europe","HRV":"Europe","CYP":"Europe","CZE":"Europe",
        "DNK":"Europe","EST":"Europe","FIN":"Europe","FRA":"Europe","DEU":"Europe",
        "GRC":"Europe","HUN":"Europe","ISL":"Europe","IRL":"Europe","ITA":"Europe",
        "LVA":"Europe","LIE":"Europe","LTU":"Europe","LUX":"Europe","MLT":"Europe",
        "MDA":"Europe","MCO":"Europe","MNE":"Europe","NLD":"Europe","MKD":"Europe",
        "NOR":"Europe","POL":"Europe","PRT":"Europe","ROU":"Europe","RUS":"Europe",
        "SMR":"Europe","SRB":"Europe","SVK":"Europe","SVN":"Europe","ESP":"Europe",
        "SWE":"Europe","CHE":"Europe","UKR":"Europe","GBR":"Europe","VAT":"Europe",
        "XKX":"Europe","GRL":"Europe","FRO":"Europe",
        "ATG":"Americas","ARG":"Americas","BHS":"Americas","BRB":"Americas",
        "BLZ":"Americas","BOL":"Americas","BRA":"Americas","CAN":"Americas",
        "CHL":"Americas","COL":"Americas","CRI":"Americas","CUB":"Americas",
        "DMA":"Americas","DOM":"Americas","ECU":"Americas","SLV":"Americas",
        "GRD":"Americas","GTM":"Americas","GUY":"Americas","HTI":"Americas",
        "HND":"Americas","JAM":"Americas","MEX":"Americas","NIC":"Americas",
        "PAN":"Americas","PRY":"Americas","PER":"Americas","KNA":"Americas",
        "LCA":"Americas","VCT":"Americas","SUR":"Americas","TTO":"Americas",
        "URY":"Americas","USA":"Americas","VEN":"Americas",
        "AUS":"Oceania","FJI":"Oceania","KIR":"Oceania","MHL":"Oceania",
        "FSM":"Oceania","NRU":"Oceania","NZL":"Oceania","PLW":"Oceania",
        "PNG":"Oceania","WSM":"Oceania","SLB":"Oceania","TON":"Oceania",
        "TUV":"Oceania","VUT":"Oceania",
    }

    REGION_COLOURS = {
        "Africa":   "#E8820C",
        "Asia":     "#5B9BD5",
        "Europe":   "#2E8B57",
        "Americas": "#D95F4B",
        "Oceania":  "#9B59B6",
    }

    year_df = df[(df["year"] >= selected_years[0]) & (df["year"] <= selected_years[1])]
    bubble_source = year_df[year_df["country"].isin(selected_countries)] if bubble_filter else year_df
    summary_df = (
        bubble_source.groupby("country", as_index=False)
        .agg(
            avg_fx=("exchange_rate", "mean"),
            avg_gdp=("gdp_per_capita", "mean"),
            avg_pov=("poverty_headcount", "mean"),
            iso3=("iso3", "first")
        )
        .dropna(subset=["avg_fx", "avg_pov", "avg_gdp"])
    )

    # Cap exchange rate at 1500 LCU to prevent extreme outliers collapsing the scale
    summary_df["avg_fx_capped"] = summary_df["avg_fx"].clip(upper=1500)
    summary_df["region"] = summary_df["iso3"].map(REGION_MAP).fillna("Other")

    if bubble_filter:
        bubble_colour_col = "country"
        bubble_colour_map = selected_colour_map
        bubble_legend_title = "Country"
    else:
        bubble_colour_col = "region"
        bubble_colour_map = REGION_COLOURS
        bubble_legend_title = "Region"

    fig_bubble = px.scatter(
        summary_df,
        x="avg_fx_capped",
        y="avg_pov",
        size="avg_gdp",
        color=bubble_colour_col,
        color_discrete_map=bubble_colour_map,
        hover_name="country",
        log_x=True,
        size_max=40,
        labels={
            "avg_fx_capped": "Avg Exchange Rate (LCU per US$, log scale)",
            "avg_pov":        "Avg Poverty Headcount (%)",
            "avg_gdp":        "Avg GDP per Capita (US$)",
            "region":         "Region",
            "country":        "Country",
        },
        hover_data={
            "avg_fx":         ":.1f",
            "avg_fx_capped":  False,
            "avg_pov":        ":.1f",
            "avg_gdp":        ":,.0f",
            "region":         False,
        }
    )
    fig_bubble.update_layout(
        margin=dict(t=10),
        yaxis=dict(range=[0, 85]),
        xaxis=dict(
            tickvals=[0.1, 1, 10, 100, 1000],
            ticktext=["0.1", "1", "10", "100", "1,000"],
        ),
        legend=dict(
            title=bubble_legend_title,
            orientation="v",
            traceorder="normal"
        ),
        height=520
    )
    st.plotly_chart(fig_bubble, use_container_width=True)


# Trends tab
with tab2:
    st.header("Trends Over Time")

    if filtered.empty:
        st.info("No data available for the current selection.")
    else:

        # Exchange rate level chart
        normalise_fx = st.toggle(
            "Normalise exchange rate to base year (index = 100)",
            value=False,
            help=(
                "When on, all countries start at 100 in the first selected year, "
                "showing percentage change over time rather than absolute values. "
                "Useful for comparing currencies with very different magnitudes."
            )
        )

        fx_df = filtered.dropna(subset=["exchange_rate"]).copy()

        if normalise_fx:
            base_year = fx_df["year"].min()
            base = (
                fx_df[fx_df["year"] == base_year][["country", "exchange_rate"]]
                .rename(columns={"exchange_rate": "base_val"})
            )
            fx_df = fx_df.merge(base, on="country", how="left")
            fx_df["exchange_rate"] = (fx_df["exchange_rate"] / fx_df["base_val"]) * 100
            fx_title   = f"Exchange Rate Index Over Time (base = {base_year}, index = 100)"
            fx_y_label = f"Exchange Rate Index ({base_year} = 100)"
            fx_y_type  = "linear"
        else:
            fx_title   = "Official Exchange Rate Over Time"
            fx_y_label = "Exchange Rate (LCU per US$, log scale)"
            fx_y_type  = "log"

        st.subheader(fx_title)
        if normalise_fx:
            st.markdown(
                "Each country's exchange rate has been rebased so that its value in the first "
                "selected year equals 100. A rising line means the currency has lost value "
                "against the dollar since that base year; a falling line means it has strengthened. "
                "This makes it straightforward to compare currency trajectories regardless of how "
                "different the starting values were."
            )
        else:
            st.markdown(
                "This chart shows the official exchange rate for each selected country; that is, "
                "how many units of local currency were needed to buy one US dollar in each year. "
                "A rising line indicates currency depreciation. Because currencies like the Indian "
                "rupee and the Japanese yen operate on very different scales, a log axis is used "
                "so all countries remain visible and comparable."
            )
            st.caption("Log scale used to allow comparison across currencies with very different magnitudes.")

        fig_fx = px.line(
            fx_df.sort_values("year"),
            x="year",
            y="exchange_rate",
            color="country",
            color_discrete_map=selected_colour_map,
            markers=True,
            labels={
                "exchange_rate": fx_y_label,
                "year": "Year",
                "country": "Country"
            }
        )
        fig_fx.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            margin=dict(t=10)
        )
        if fx_y_type == "log":
            fig_fx.update_yaxes(
                type="log",
                title_text=fx_y_label,
                tickvals=[0.1, 0.5, 1, 5, 10, 50, 100, 500],
                ticktext=["0.1", "0.5", "1", "5", "10", "50", "100", "500"],
            )
        else:
            fig_fx.update_yaxes(type="linear", title_text=fx_y_label)
        fig_fx.update_xaxes(dtick=2)
        st.plotly_chart(fig_fx, use_container_width=True)

        st.divider()

        # Year-on-year volatility chart
        st.subheader("Exchange Rate Volatility Over Time")
        st.markdown(
            "This chart shows the year-on-year percentage change in each country's exchange "
            "rate. Where the level chart above shows direction, this one shows pace; large "
            "swings above or below the zero line indicate periods of instability. Sustained "
            "volatility can make it harder for households and governments in developing "
            "economies to plan, borrow, or import essential goods."
        )
        st.caption(
            "Positive values indicate currency depreciation against the dollar; "
            "negative values indicate appreciation."
        )

        vol_df = fx_df.sort_values(["country", "year"]).copy()
        if normalise_fx:
            # Recalculate from raw data to get meaningful volatility figures
            raw_fx = filtered.dropna(subset=["exchange_rate"]).copy()
            vol_df = raw_fx.sort_values(["country", "year"])

        vol_df["fx_change_pct"] = (
            vol_df.groupby("country")["exchange_rate"]
            .pct_change() * 100
        )
        vol_df = vol_df.dropna(subset=["fx_change_pct"])

        if vol_df.empty:
            st.info("Not enough data points to calculate year-on-year change. Try expanding the year range.")
        else:
            fig_vol = px.line(
                vol_df.sort_values("year"),
                x="year",
                y="fx_change_pct",
                color="country",
                color_discrete_map=selected_colour_map,
                markers=True,
                labels={
                    "fx_change_pct": "Exchange Rate Change (%)",
                    "year": "Year",
                    "country": "Country"
                }
            )
            fig_vol.add_hline(
                y=0,
                line_dash="dash",
                line_color="rgba(255,255,255,0.3)",
                annotation_text="No change",
                annotation_position="bottom right"
            )
            fig_vol.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                hovermode="x unified",
                margin=dict(t=10)
            )
            fig_vol.update_xaxes(dtick=2)
            st.plotly_chart(fig_vol, use_container_width=True)

        st.divider()

        # GDP chart
        normalise_gdp = st.toggle(
            "Normalise GDP to base year (index = 100)",
            value=False,
            help=(
                "When on, shows GDP growth relative to the first selected year rather than "
                "absolute values. Useful for comparing growth rates across countries with "
                "very different income levels."
            )
        )

        gdp_df = filtered.dropna(subset=["gdp_per_capita"]).copy()

        # Warn if income spread is so wide that low-GDP countries will be nearly invisible
        if not gdp_df.empty and not normalise_gdp:
            gdp_spread = gdp_df.groupby("country")["gdp_per_capita"].mean()
            if gdp_spread.max() / max(gdp_spread.min(), 1) > 10:
                st.info(
                    "The selected countries have very different income levels; some lines may "
                    "appear nearly flat at the bottom of the chart. Enable the normalise toggle "
                    "above to compare growth rates instead of absolute values."
                )

        if normalise_gdp:
            base_year_gdp = gdp_df["year"].min()
            base_gdp = (
                gdp_df[gdp_df["year"] == base_year_gdp][["country", "gdp_per_capita"]]
                .rename(columns={"gdp_per_capita": "base_val"})
            )
            gdp_df = gdp_df.merge(base_gdp, on="country", how="left")
            gdp_df["gdp_per_capita"] = (gdp_df["gdp_per_capita"] / gdp_df["base_val"]) * 100
            gdp_title   = f"GDP per Capita Index Over Time (base = {base_year_gdp}, index = 100)"
            gdp_y_label = f"GDP per Capita Index ({base_year_gdp} = 100)"
            gdp_y_type  = "linear"
            # Check if one country dominates and compress others
            gdp_max_idx = (gdp_df.groupby("country")["gdp_per_capita"].mean().max()
                           / max(gdp_df.groupby("country")["gdp_per_capita"].mean().min(), 1))
            if gdp_max_idx > 3:
                st.info(
                    "One or more countries have grown significantly faster than others; "
                    "they may compress the rest of the chart. This reflects real differences "
                    "in growth rates and is not an error."
                )
        else:
            gdp_title   = "GDP per Capita Over Time"
            gdp_y_label = "GDP per Capita (US$)"
            gdp_y_type  = "linear"

        st.subheader(gdp_title)
        if normalise_gdp:
            st.markdown(
                "GDP per capita has been rebased so that each country's value in the first "
                "selected year equals 100. This removes the effect of absolute income differences "
                "and lets you compare how quickly each economy has grown or contracted, "
                "relative to its own starting point."
            )
        else:
            st.markdown(
                "This chart tracks GDP per capita in current US dollars for each selected country "
                "over time. It gives a sense of how living standards have evolved and how far apart "
                "income levels are between countries. Use the normalise toggle to compare growth "
                "rates rather than absolute values."
            )
            st.caption(
                "Select countries with similar income levels for best comparison, "
                "or enable the normalise toggle above."
            )

        fig_gdp = px.line(
            gdp_df.sort_values("year"),
            x="year",
            y="gdp_per_capita",
            color="country",
            color_discrete_map=selected_colour_map,
            markers=True,
            labels={
                "gdp_per_capita": gdp_y_label,
                "year": "Year",
                "country": "Country"
            }
        )
        fig_gdp.update_layout(
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified",
            margin=dict(t=10)
        )
        fig_gdp.update_yaxes(type=gdp_y_type, title_text=gdp_y_label, tickformat=",.0f")
        fig_gdp.update_xaxes(dtick=2)
        st.plotly_chart(fig_gdp, use_container_width=True)


# Compare tab
with tab3:
    st.header("Country Comparison")
    st.caption(
        "Compare how GDP and exchange rates changed across the selected year range, "
        "and view average poverty headcount across selected countries."
    )

    if filtered.empty:
        st.info("No data available for the current selection.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("GDP Growth vs Exchange Rate Change")
            st.markdown(
                "Each dot represents one country, positioned by how much its exchange rate "
                "and GDP per capita changed across the selected year range. Countries in the "
                "top-left strengthened their currency and grew richer; countries in the "
                "top-right saw their currency weaken but still grew. The bottom quadrants "
                "indicate falling GDP. Hover any dot for exact figures."
            )
            st.caption(
                "Percentage change from the first to the last year in the selected range. "
                "Positive exchange rate change means the currency weakened against the dollar."
            )

            scatter_df = filtered.dropna(subset=["gdp_per_capita", "exchange_rate"]).copy()
            scatter_df = scatter_df.sort_values("year")

            sorted_df = scatter_df.sort_values("year")
            quad_first = (
                sorted_df.groupby("country")[["exchange_rate", "gdp_per_capita", "year"]]
                .first().reset_index()
                .rename(columns={"exchange_rate": "fx_start", "gdp_per_capita": "gdp_start", "year": "year_start"})
            )
            quad_last = (
                sorted_df.groupby("country")[["exchange_rate", "gdp_per_capita", "year"]]
                .last().reset_index()
                .rename(columns={"exchange_rate": "fx_end", "gdp_per_capita": "gdp_end", "year": "year_end"})
            )
            change_df = quad_first.merge(quad_last, on="country")
            change_df["fx_change_pct"]  = (change_df["fx_end"]  - change_df["fx_start"])  / change_df["fx_start"]  * 100
            change_df["gdp_change_pct"] = (change_df["gdp_end"] - change_df["gdp_start"]) / change_df["gdp_start"] * 100

            x_max = max(change_df["fx_change_pct"].abs().max() * 1.4, 10)
            y_max = max(change_df["gdp_change_pct"].abs().max() * 1.4, 10)

            fig_scatter = go.Figure()

            for x0, x1, y0, y1, colour, label in [
                (0,     x_max,  0,      y_max,  "rgba(46,139,87,0.08)",  "Currency weakened, GDP grew"),
                (-x_max, 0,     0,      y_max,  "rgba(91,155,213,0.08)", "Currency strengthened, GDP grew"),
                (0,     x_max,  -y_max, 0,      "rgba(217,95,75,0.08)",  "Currency weakened, GDP fell"),
                (-x_max, 0,     -y_max, 0,      "rgba(155,89,182,0.08)", "Currency strengthened, GDP fell"),
            ]:
                fig_scatter.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                                      fillcolor=colour, line_width=0, layer="below")
                fig_scatter.add_annotation(
                    x=(x0 + x1) / 2, y=(y0 + y1) / 2,
                    text=label, showarrow=False,
                    font=dict(size=10, color="rgba(255,255,255,0.3)"),
                )

            fig_scatter.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.25)")
            fig_scatter.add_vline(x=0, line_dash="dash", line_color="rgba(255,255,255,0.25)")

            for _, row in change_df.iterrows():
                colour = selected_colour_map.get(row["country"], "#888888")
                fig_scatter.add_trace(go.Scatter(
                    x=[row["fx_change_pct"]],
                    y=[row["gdp_change_pct"]],
                    mode="markers+text",
                    marker=dict(size=14, color=colour),
                    text=[row["country"]],
                    textposition="top center",
                    name=row["country"],
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{row['country']}</b><br>"
                        f"Period: {int(row['year_start'])} to {int(row['year_end'])}<br>"
                        f"Exchange rate change: {row['fx_change_pct']:+.1f}%<br>"
                        f"GDP per capita change: {row['gdp_change_pct']:+.1f}%"
                        "<extra></extra>"
                    ),
                ))

            fig_scatter.update_layout(
                xaxis=dict(title="Exchange Rate Change (%, positive = currency weakened)",
                           range=[-x_max, x_max], zeroline=False),
                yaxis=dict(title="GDP per Capita Change (%)",
                           range=[-y_max, y_max], zeroline=False),
                hovermode="closest",
                margin=dict(t=10),
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

        with col2:
            st.subheader("Average Poverty Headcount (%)")
            st.markdown(
                "This chart shows the average share of each country's population living below "
                "$2.15 per day, averaged across the selected year range. It allows a direct "
                "comparison of poverty levels between the countries in your current selection; "
                "and when read alongside the trajectory scatter, it helps reveal whether countries "
                "with more exchange rate volatility also tend to have higher poverty rates."
            )
            st.caption(
                "Average across the selected year range. "
                "Countries with no survey data are excluded."
            )

            # Split selected countries into those with and without poverty data
            pov_has = (
                filtered.dropna(subset=["poverty_headcount"])
                .groupby("country", as_index=False)["poverty_headcount"]
                .mean()
            )
            pov_missing = sorted(
                set(selected_countries) - set(pov_has["country"])
            )

            if pov_has.empty:
                st.info(
                    "No poverty data available for the selected countries and year range. "
                    "Try expanding the year range or selecting different countries."
                )
            else:
                if pov_missing:
                    missing_rows = pd.DataFrame({
                        "country": pov_missing,
                        "poverty_headcount": [0.0] * len(pov_missing),
                    })
                    pov_df = pd.concat([pov_has, missing_rows], ignore_index=True)
                else:
                    pov_df = pov_has.copy()

                pov_df = pov_df.sort_values("poverty_headcount", ascending=False)
                pov_df["has_data"] = pov_df["country"].isin(pov_has["country"])

                pov_max = pov_has["poverty_headcount"].max()

                fig_bar = go.Figure()

                for _, row in pov_df.iterrows():
                    if row["has_data"]:
                        ratio = row["poverty_headcount"] / max(pov_max, 1)
                        r = int(192 + (74 - 192) * ratio)
                        g = int(57 + (0  - 57)  * ratio)
                        b = int(43 + (0  - 43)  * ratio)
                        colour = f"rgb({r},{g},{b})"
                        hover  = f"{row['country']}: {row['poverty_headcount']:.1f}%<extra></extra>"
                        label  = f"{row['poverty_headcount']:.1f}"
                    else:
                        colour = "#555555"
                        hover  = "No survey data available<extra></extra>"
                        label  = "No data"

                    fig_bar.add_trace(go.Bar(
                        x=[row["country"]],
                        y=[row["poverty_headcount"] if row["has_data"] else 0.5],
                        marker_color=colour,
                        showlegend=False,
                        text=label,
                        textposition="outside",
                        hovertemplate=hover,
                    ))

                fig_bar.update_layout(
                    showlegend=False,
                    xaxis_tickangle=-30,
                    yaxis_title="Avg Poverty Headcount (%)",
                    xaxis_title="Country",
                    margin=dict(t=10),
                    bargap=0.3,
                )
                st.plotly_chart(fig_bar, use_container_width=True)

                if pov_missing:
                    missing_str = ", ".join(pov_missing)
                    st.caption(
                        f"Grey bars indicate no poverty survey data available for: {missing_str}. "
                        "All other countries show the average headcount across the selected year range."
                    )
                else:
                    st.caption(
                        "Darker bars indicate higher average poverty. "
                        "Countries shown have at least one survey data point in the selected year range."
                    )


# About tab
with tab4:
    st.header("About This Dashboard")
    st.markdown("""
    **Data source:** World Development Indicators (WDI), World Bank, Version 128, April 2026

    **Indicators used:**
    - `PA.NUS.FCRF`: Official exchange rate (LCU per US$, period average)
    - `NY.GDP.PCAP.CD`: GDP per capita (current US$)
    - `SI.POV.DDAY`: Poverty headcount ratio at $2.15/day (% of population)

    **Coverage:** 217 sovereign countries, 2000–2024

    **Purpose:**
    This dashboard explores the relationship between currency exchange rate volatility
    and sustainable development outcomes across fragile and developing states.
    Exchange rate instability erodes household purchasing power and raises the cost
    of imported goods, both of which bear directly on poverty outcomes. Presenting
    these three indicators together allows users to examine whether countries with
    more volatile exchange rates also tend to have lower GDP per capita and higher
    poverty rates.

    **How to use the Trends tab:**
    The normalise toggle on both the exchange rate and GDP charts converts absolute
    values into an index (base year = 100), making it possible to compare growth
    rates across countries with very different currency magnitudes or income levels.
    Turn it on when selecting a mixed group of countries (for example, Japan, India,
    and Spain together). The volatility chart below the exchange rate chart shows
    year-on-year percentage change, making periods of currency instability clearly
    visible regardless of the normalise toggle.

    **How to use the Overview tab:**
    The bubble chart plots every country by its average exchange rate and average poverty
    headcount. Use the "Show selected countries only" toggle above the chart to switch
    between the full global view and a focused view of your sidebar selection. In the
    filtered view, bubble colours match the country colours used across all other charts.
    In the global view, colours indicate world region.

    **How to use the Compare tab:**
    The quadrant scatter shows the total percentage change in exchange rate and GDP
    per capita from the first to the last year in the selected range. Each dot is one
    country. The four shaded quadrants make the direction of each outcome immediately
    readable: top-right means the currency weakened but GDP still grew; top-left means
    both the currency strengthened and GDP grew; bottom quadrants indicate falling GDP.
    The poverty bar chart shows the average headcount for each selected country.
    Countries with no survey data appear as grey bars labelled "No data" rather than
    being silently excluded, so the absence of data is always visible.

    **Note on data completeness:**
    Poverty headcount data (SI.POV.DDAY) relies on household surveys, which are
    conducted infrequently in many low-income countries. Gaps in the poverty column
    are expected and reflect the availability of survey data rather than an error
    in the dashboard.

    **Built with:** Python · Streamlit · Plotly Express · Pandas

    **Author:** Oscar Denche (w2111719), 5DATA004W, University of Westminster, 2026
    """)