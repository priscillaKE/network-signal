# Power BI Dashboard Guide

This guide documents the Network Overview report built from the
`public vw_powerbi_network_telemetry` table.

## Data source

Connect Power BI Desktop to PostgreSQL using:

- Server: `localhost`
- Database: `telecom_qos_db`
- Table: `public vw_powerbi_network_telemetry`

Use Import mode and select the view rather than the raw telemetry table.

## Measures

Create each formula as a separate measure from the table shown above:

```DAX
Average QoS Score =
AVERAGE('public vw_powerbi_network_telemetry'[qos_score])
```

```DAX
Average Signal =
AVERAGE('public vw_powerbi_network_telemetry'[signal_strength_dbm])
```

```DAX
Issue Rate =
DIVIDE(
    CALCULATE(
        COUNTROWS('public vw_powerbi_network_telemetry'),
        'public vw_powerbi_network_telemetry'[network_issue_flag] = TRUE()
    ),
    COUNTROWS('public vw_powerbi_network_telemetry')
)
```

```DAX
Dropped Call Rate =
DIVIDE(
    CALCULATE(
        COUNTROWS('public vw_powerbi_network_telemetry'),
        'public vw_powerbi_network_telemetry'[call_dropped_flag] = TRUE()
    ),
    COUNTROWS('public vw_powerbi_network_telemetry')
)
```

Format `Average QoS Score` as a decimal number, not a percentage. Format
`Issue Rate` and `Dropped Call Rate` as percentages.

## Network Overview page

Page title:

> Uganda Mobile Network Quality Overview

Place four Card visuals across the top:

1. `Average QoS Score`
2. `Average Signal`
3. `Issue Rate`
4. `Dropped Call Rate`

Add these visuals underneath:

- Line chart: `observation_date` on the X-axis and `Average QoS Score` on the Y-axis.
- Clustered bar chart: `district` on the Y-axis and `Average QoS Score` on the X-axis, sorted descending.
- Donut chart: `network_type` as the legend and count of `telemetry_id` as the value.

Add slicers for `district`, `network_type`, and `device_model`. Use
`observation_date` as an optional date slicer.

## Visual style

Use a restrained operations-dashboard palette:

- Page background: `#F4F6F8`
- Card background: `#FFFFFF`
- Primary blue: `#087FC1`
- Teal: `#078C8C`
- Warning amber: `#FFBE0B`
- Critical red: `#F00000`
- Text: `#17202A`

Keep the KPI cards equal in size and aligned horizontally. Give the line and
district charts most of the page width, and keep slicers grouped together so
they do not compete with the main visuals.

## Recommended interactions

- Select a district to filter every visual on the page.
- Select a network type or device model to compare performance segments.
- Use the line chart to inspect QoS changes across the observation period.
- Use the district chart to identify the strongest and weakest areas.
