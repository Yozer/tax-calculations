# Etoro Taxes

## Common Issues
```
Exception: Found a rollover fee for crypto position {id}. Should be marked as cfd?
```
Check if position was leveraged. 
If yes, then in 'Closed Positions' sheet add 'CFD' value to 'Is Real' column, and enter correct leverage in 'Leverage' column.
