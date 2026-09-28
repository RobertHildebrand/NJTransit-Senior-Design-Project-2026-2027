# Prototype results

Timetable verification: min opposing separation on single track = 0.50 min (>= 0.5 required); violations: none

## Headway ladder (clock-face headways)

|   T |   trainsets |   cycle_min |   nb_trip_min |   sb_trip_min |   layover_trenton |   layover_camden |   added_wait_min |
|----:|------------:|------------:|--------------:|--------------:|------------------:|-----------------:|-----------------:|
|  15 |          10 |         150 |          67   |          67   |               5.3 |             10.7 |              0   |
|  16 |          10 |         160 |          67   |          67   |               9   |             17   |              0   |
|  20 |           9 |         180 |          68.2 |          83.9 |              18.9 |              9   |             18.1 |
|  24 |           7 |         168 |          67   |          67   |               9   |             25   |              0   |
|  26 |           6 |         156 |          67   |          67.7 |              15.8 |              5.5 |              0.7 |
|  30 |           5 |         150 |          67   |          67   |               5   |             11   |              0   |
|  60 |           3 |         180 |          67   |          67   |               5   |             41   |              0   |

## Plan ladder: cars at 6 am -> plan

|   cars_available | clockface_r0       | clockface_r1       | flex_r1            |
|-----------------:|:-------------------|:-------------------|:-------------------|
|                3 | 60 min (3 trains)  | bus bridge         | bus bridge         |
|                4 | 60 min (3 trains)  | 60 min (3 trains)  | 52 min (3 trains)  |
|                5 | 30 min (5 trains)  | 60 min (3 trains)  | 38 min (4 trains)  |
|                6 | 30 min (5 trains)  | 30 min (5 trains)  | 29 min (5 trains)  |
|                7 | 30 min (5 trains)  | 30 min (5 trains)  | 26 min (6 trains)  |
|                8 | 30 min (5 trains)  | 30 min (5 trains)  | 23 min (7 trains)  |
|                9 | 20 min (9 trains)  | 30 min (5 trains)  | 21 min (8 trains)  |
|               10 | 15 min (10 trains) | 20 min (9 trains)  | 19 min (9 trains)  |
|               11 | 15 min (10 trains) | 15 min (10 trains) | 15 min (10 trains) |
|               12 | 15 min (10 trains) | 15 min (10 trains) | 15 min (10 trains) |
|               13 | 15 min (10 trains) | 15 min (10 trains) | 15 min (10 trains) |
|               14 | 15 min (10 trains) | 15 min (10 trains) | 15 min (10 trains) |

## Policy comparison (30 reps x 365 weekdays)

| policy                     |   mean cars available |   published trips/day |   cancelled % of published |   on-time % of published |   in-service failures/day |   avg wait (min) |   avg wait vs published (min) |   impact score |
|:---------------------------|----------------------:|----------------------:|---------------------------:|-------------------------:|--------------------------:|-----------------:|------------------------------:|---------------:|
| Fixed 8-car (20/30)        |                  8.7  |                 80    |                       9.68 |                    84.1  |                      0.65 |            16.9  |                          4.54 |          21.43 |
| Tiered clockface, no spare |                  8.56 |                 76.29 |                       1.96 |                    91.21 |                      0.67 |            14.8  |                          0.79 |          15.58 |
| Tiered clockface, 1 spare  |                  9.03 |                 73.41 |                       0.86 |                    92.27 |                      0.63 |            14.91 |                          0.35 |          15.26 |
| Tiered flexible, 1 spare   |                  8.77 |                 76.54 |                       1.06 |                    91.99 |                      0.67 |            14.08 |                          0.42 |          14.5  |
| Tiered flexible, 2 spares  |                  8.89 |                 71.68 |                       0.73 |                    92.39 |                      0.64 |            15.11 |                          0.32 |          15.43 |

## By season

|                                          |   cancel % |   on-time % pub |   avg wait |   cars avail |
|:-----------------------------------------|-----------:|----------------:|-----------:|-------------:|
| ('Fixed 8-car (20/30)', 'fall')          |        7.2 |            83.5 |       15.4 |          9.1 |
| ('Fixed 8-car (20/30)', 'spring')        |        5.4 |            90.9 |       14.6 |          9.8 |
| ('Fixed 8-car (20/30)', 'summer')        |       16   |            78.5 |       20.6 |          7.5 |
| ('Fixed 8-car (20/30)', 'winter')        |       10.1 |            83.4 |       17   |          8.4 |
| ('Tiered clockface, 1 spare', 'fall')    |        0.7 |            89.3 |       14.4 |          9.2 |
| ('Tiered clockface, 1 spare', 'spring')  |        0.5 |            95.4 |       13   |         10.2 |
| ('Tiered clockface, 1 spare', 'summer')  |        1.5 |            92.1 |       17.3 |          7.9 |
| ('Tiered clockface, 1 spare', 'winter')  |        0.9 |            91.9 |       15   |          8.8 |
| ('Tiered clockface, no spare', 'fall')   |        1.6 |            88.4 |       14   |          8.9 |
| ('Tiered clockface, no spare', 'spring') |        1.1 |            94.8 |       12.5 |         10   |
| ('Tiered clockface, no spare', 'summer') |        3.4 |            90.3 |       17.9 |          7.1 |
| ('Tiered clockface, no spare', 'winter') |        2   |            90.9 |       14.8 |          8.3 |
| ('Tiered flexible, 1 spare', 'fall')     |        0.9 |            89   |       13.7 |          8.9 |
| ('Tiered flexible, 1 spare', 'spring')   |        0.6 |            95.4 |       12.5 |          9.9 |
| ('Tiered flexible, 1 spare', 'summer')   |        1.8 |            91.7 |       15.9 |          7.8 |
| ('Tiered flexible, 1 spare', 'winter')   |        1.1 |            91.6 |       14.2 |          8.5 |
| ('Tiered flexible, 2 spares', 'fall')    |        0.6 |            89.3 |       14.4 |          9.1 |
| ('Tiered flexible, 2 spares', 'spring')  |        0.5 |            95.5 |       13.4 |         10   |
| ('Tiered flexible, 2 spares', 'summer')  |        1.1 |            92.5 |       17   |          7.9 |
| ('Tiered flexible, 2 spares', 'winter')  |        0.8 |            92   |       15.7 |          8.5 |