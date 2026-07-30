# Fixed-Recurrence Mechanism Study

**Diagnostic verdict: MECHANISM-UNRESOLVED**

This training-only study uses 30 seeds (8000–8029). It sweeps rho and reports tau = -dt/log(rho) across target-change timescales. It is a mechanism diagnostic, not a new promotion test.

## Correlations

- Between-cell RMSE improvement vs diversity change: `-0.2949767494775837`
- Within-cell paired RMSE improvement vs diversity change: `0.05065449197094272`
- Within-cell paired RMSE improvement vs disagreement change: `-0.0634654836488019`
- Within-cell paired RMSE improvement vs information change: `0.3447518186567666`

## Best recurrence by scenario

| Scenario | Best rho | Tau | Scenario timescale | Tau/timescale | RMSE |
|---|---:|---:|---:|---:|---:|
| abrupt_change | 0.93 | 13.780 | 80.0 | 0.1722 | 0.6443 |
| gradual_10 | 0.72 | 3.044 | 10.0 | 0.3044 | 0.6359 |
| gradual_20 | 0.93 | 13.780 | 20.0 | 0.6890 | 0.6345 |
| gradual_40 | 0.85 | 6.153 | 40.0 | 0.1538 | 0.6358 |
| no_change | 0.85 | 6.153 | 160.0 | 0.0385 | 0.6341 |
| repeated_20 | 0.72 | 3.044 | 20.0 | 0.1522 | 0.6675 |
| repeated_35 | 0.85 | 6.153 | 35.0 | 0.1758 | 0.6668 |
| repeated_50 | 0.85 | 6.153 | 50.0 | 0.1231 | 0.6534 |

## Full cell means

| Scenario | Rho | Tau | RMSE | Diversity | Disagreement | Information |
|---|---:|---:|---:|---:|---:|---:|
| no_change | 0.00 | 0.000 | 0.6816 | 4.877 | 0.555 | 3.502 |
| no_change | 0.25 | 0.721 | 0.6484 | 4.809 | 0.545 | 3.598 |
| no_change | 0.50 | 1.443 | 0.6419 | 4.777 | 0.493 | 3.675 |
| no_change | 0.72 | 3.044 | 0.6462 | 4.771 | 0.372 | 3.721 |
| no_change | 0.85 | 6.153 | 0.6341 | 4.768 | 0.326 | 3.736 |
| no_change | 0.93 | 13.780 | 0.6374 | 4.768 | 0.330 | 3.733 |
| abrupt_change | 0.00 | 0.000 | 0.7315 | 4.866 | 0.593 | 3.382 |
| abrupt_change | 0.25 | 0.721 | 0.6950 | 4.808 | 0.570 | 3.504 |
| abrupt_change | 0.50 | 1.443 | 0.6589 | 4.776 | 0.525 | 3.619 |
| abrupt_change | 0.72 | 3.044 | 0.6588 | 4.769 | 0.432 | 3.698 |
| abrupt_change | 0.85 | 6.153 | 0.6603 | 4.768 | 0.358 | 3.723 |
| abrupt_change | 0.93 | 13.780 | 0.6443 | 4.767 | 0.350 | 3.724 |
| gradual_10 | 0.00 | 0.000 | 0.7227 | 4.870 | 0.587 | 3.391 |
| gradual_10 | 0.25 | 0.721 | 0.6796 | 4.809 | 0.570 | 3.512 |
| gradual_10 | 0.50 | 1.443 | 0.6560 | 4.775 | 0.524 | 3.623 |
| gradual_10 | 0.72 | 3.044 | 0.6359 | 4.772 | 0.424 | 3.701 |
| gradual_10 | 0.85 | 6.153 | 0.6417 | 4.768 | 0.347 | 3.727 |
| gradual_10 | 0.93 | 13.780 | 0.6414 | 4.769 | 0.341 | 3.728 |
| gradual_20 | 0.00 | 0.000 | 0.7154 | 4.869 | 0.586 | 3.404 |
| gradual_20 | 0.25 | 0.721 | 0.6772 | 4.809 | 0.565 | 3.521 |
| gradual_20 | 0.50 | 1.443 | 0.6504 | 4.775 | 0.520 | 3.629 |
| gradual_20 | 0.72 | 3.044 | 0.6397 | 4.774 | 0.419 | 3.703 |
| gradual_20 | 0.85 | 6.153 | 0.6405 | 4.770 | 0.347 | 3.728 |
| gradual_20 | 0.93 | 13.780 | 0.6345 | 4.769 | 0.335 | 3.731 |
| gradual_40 | 0.00 | 0.000 | 0.6989 | 4.870 | 0.578 | 3.429 |
| gradual_40 | 0.25 | 0.721 | 0.6647 | 4.809 | 0.559 | 3.541 |
| gradual_40 | 0.50 | 1.443 | 0.6427 | 4.777 | 0.513 | 3.640 |
| gradual_40 | 0.72 | 3.044 | 0.6448 | 4.770 | 0.408 | 3.708 |
| gradual_40 | 0.85 | 6.153 | 0.6358 | 4.767 | 0.342 | 3.730 |
| gradual_40 | 0.93 | 13.780 | 0.6403 | 4.769 | 0.335 | 3.731 |
| repeated_20 | 0.00 | 0.000 | 0.7048 | 4.875 | 0.545 | 3.530 |
| repeated_20 | 0.25 | 0.721 | 0.6967 | 4.810 | 0.535 | 3.608 |
| repeated_20 | 0.50 | 1.443 | 0.6807 | 4.777 | 0.488 | 3.674 |
| repeated_20 | 0.72 | 3.044 | 0.6675 | 4.772 | 0.383 | 3.714 |
| repeated_20 | 0.85 | 6.153 | 0.6777 | 4.769 | 0.354 | 3.723 |
| repeated_20 | 0.93 | 13.780 | 0.6762 | 4.772 | 0.371 | 3.714 |
| repeated_35 | 0.00 | 0.000 | 0.7086 | 4.876 | 0.550 | 3.521 |
| repeated_35 | 0.25 | 0.721 | 0.6856 | 4.808 | 0.546 | 3.605 |
| repeated_35 | 0.50 | 1.443 | 0.6761 | 4.778 | 0.494 | 3.673 |
| repeated_35 | 0.72 | 3.044 | 0.6728 | 4.772 | 0.382 | 3.715 |
| repeated_35 | 0.85 | 6.153 | 0.6668 | 4.767 | 0.352 | 3.725 |
| repeated_35 | 0.93 | 13.780 | 0.6672 | 4.769 | 0.365 | 3.718 |
| repeated_50 | 0.00 | 0.000 | 0.6885 | 4.876 | 0.551 | 3.514 |
| repeated_50 | 0.25 | 0.721 | 0.6777 | 4.809 | 0.543 | 3.600 |
| repeated_50 | 0.50 | 1.443 | 0.6702 | 4.777 | 0.492 | 3.673 |
| repeated_50 | 0.72 | 3.044 | 0.6662 | 4.772 | 0.377 | 3.717 |
| repeated_50 | 0.85 | 6.153 | 0.6534 | 4.768 | 0.343 | 3.729 |
| repeated_50 | 0.93 | 13.780 | 0.6586 | 4.770 | 0.359 | 3.721 |

Correlation is not mediation. A supported geometry signature motivates a causal geometry ablation; an unresolved signature means rho remains an empirical scenario-family setting.
