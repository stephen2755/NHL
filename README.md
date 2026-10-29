# NHL Daily Prediction Model

CBB-style daily card. Initial release is an **experimental baseline**, not a backtested advanced model.

## Website
GitHub Pages: https://stephen2755.github.io/NHL/

## Data
The site reads the NHL public score and standings endpoints in the browser. The baseline uses season-to-date goals for/against with regression toward league average, home-ice adjustment, and a Poisson score distribution. It does not yet use historical backtesting, goalie confirmations, expected goals, or player scoring probabilities.

## Deployment
Settings → Pages → Build and deployment → Source: GitHub Actions. The included workflow deploys on pushes to main.

## Roadmap
1. Import SportsDataverse historical NHL data and archive as-of-game features.
2. Implement walk-forward training/backtesting and score MAE calibration.
3. Add confirmed starting goalies, xG, rest, injuries, and head-to-head shrinkage.
4. Add scorer probabilities and save daily pregame predictions.
5. Add scheduled pregame refresh and prediction-grading reports.

This is not affiliated with the NHL.