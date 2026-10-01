# Call of Kiuru — Validation Log

Model predictions (USA-NPN Extended Spring Indices, SI-x) compared against
observed phenology from national open-data networks. Positive error = model late.

## Summary

| Event | Reference species | SI-x index (3-plant average) | SI-x lilac sub-model |
|---|---|---|---|
| bloom | Syringa vulgaris | 2.8 days RMSE, bias -0.5 (n=8) | 5.4 days RMSE, bias +4.6 (n=8) |
| leaf | Betula pendula | 37.8 days RMSE, bias -36.2 (n=8) | 30.2 days RMSE, bias -28.9 (n=8) |
| leaf | Syringa vulgaris | 33.6 days RMSE, bias -26.8 (n=2) | 25.0 days RMSE, bias -19.8 (n=2) |

## Entries

| Location | Year | Event | Species | Model (index) | Model (lilac) | Observed | Error (index) | n obs | Source |
|---|---|---|---|---|---|---|---|---|---|
| Berlin, Germany | 2020 | bloom | Syringa vulgaris | 115 | 120 | 116 | -1.0 | 14 | DWD |
| Cologne, Germany | 2020 | bloom | Syringa vulgaris | 103 | 108 | 106 | -3.0 | 5 | DWD |
| Frankfurt, Germany | 2020 | bloom | Syringa vulgaris | 106.7 | 111 | 107 | -0.3 | 5 | DWD |
| Gothenburg, Sweden | 2020 | bloom | Syringa vulgaris | 140 | 146 | 145.5 | -5.5 | 6 | SLU |
| Hamburg, Germany | 2020 | bloom | Syringa vulgaris | 116.3 | 122 | 117.5 | -1.2 | 2 | DWD |
| Malmo, Sweden | 2020 | bloom | Syringa vulgaris | 133 | 141 | 130.5 | +2.5 | 2 | SLU |
| Munich, Germany | 2020 | bloom | Syringa vulgaris | 115.7 | 119 | 114.5 | +1.2 | 16 | DWD |
| Stockholm, Sweden | 2020 | bloom | Syringa vulgaris | 151.7 | 155 | 148 | +3.7 | 3 | SLU |
| Berlin, Germany | 2020 | leaf | Betula pendula | 59 | 68 | 100 | -41.0 | 4 | DWD |
| Cologne, Germany | 2020 | leaf | Betula pendula | 49 | 53 | 94.5 | -45.5 | 6 | DWD |
| Frankfurt, Germany | 2020 | leaf | Betula pendula | 58.3 | 67 | 87 | -28.7 | 7 | DWD |
| Gothenburg, Sweden | 2020 | leaf | Betula pendula | 67 | 78 | 114 | -47.0 | 7 | SLU |
| Hamburg, Germany | 2020 | leaf | Betula pendula | 57.7 | 67 | 98 | -40.3 | 1 | DWD |
| Malmo, Sweden | 2020 | leaf | Betula pendula | 64 | 76 | 110.5 | -46.5 | 8 | SLU |
| Munich, Germany | 2020 | leaf | Betula pendula | 74.3 | 77 | 99 | -24.7 | 9 | DWD |
| Stockholm, Sweden | 2020 | leaf | Betula pendula | 105 | 107 | 121 | -16.0 | 12 | SLU |
| Malmo, Sweden | 2020 | leaf | Syringa vulgaris | 64 | 76 | 111 | -47.0 | 1 | SLU |
| Stockholm, Sweden | 2020 | leaf | Syringa vulgaris | 105 | 107 | 111.5 | -6.5 | 2 | SLU |
