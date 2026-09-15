# P3: почему пропадают интервалы и где возникает недопокрытие
Проверены все 800 сохранённых наборов. Метод, пороги и исходные интервалы не изменялись.
Причины ниже рассчитаны по всем исходным критериям достаточности. Строка reason в старом файле могла оставаться общей даже после исключения интервала по размеру хвоста.
| Сценарий | Метод | Доступно | Покрыто среди доступных | Интервал ниже истины | Выше истины |
|---|---|---:|---:|---:|---:|
| original_support | original percentile | 200/200 | 169/200 | 31 | 0 |
| original_support | original basic | 200/200 | 170/200 | 30 | 0 |

original_support, original: причины недоступности — {}.
| original_support | observed_support percentile | 155/200 | 149/155 | 5 | 1 |
| original_support | observed_support basic | 155/200 | 149/155 | 5 | 1 |

original_support, observed_support: причины недоступности — {'calibration_excesses below 20': 45}.
| lower_support | original percentile | 187/200 | 173/187 | 12 | 2 |
| lower_support | original basic | 187/200 | 171/187 | 9 | 7 |

lower_support, original: причины недоступности — {'failure_excesses below 50': 5, 'too few finite bootstrap fits': 3, 'failure_excesses below 50; too few finite bootstrap fits': 5}.
| lower_support | observed_support percentile | 187/200 | 173/187 | 12 | 2 |
| lower_support | observed_support basic | 187/200 | 171/187 | 9 | 7 |

lower_support, observed_support: причины недоступности — {'failure_excesses below 50': 5, 'too few finite bootstrap fits': 3, 'failure_excesses below 50; too few finite bootstrap fits': 5}.
| exponential_null | original percentile | 173/200 | 151/173 | 22 | 0 |
| exponential_null | original basic | 173/200 | 161/173 | 8 | 4 |

exponential_null, original: причины недоступности — {'too few finite bootstrap fits': 16, 'failure_excesses below 50': 3, 'failure_excesses below 50; too few finite bootstrap fits': 8}.
| exponential_null | observed_support percentile | 173/200 | 152/173 | 21 | 0 |
| exponential_null | observed_support basic | 173/200 | 161/173 | 8 | 4 |

exponential_null, observed_support: причины недоступности — {'too few finite bootstrap fits': 16, 'failure_excesses below 50': 3, 'failure_excesses below 50; too few finite bootstrap fits': 8}.
| bounded_null | original percentile | 126/200 | 119/126 | 6 | 1 |
| bounded_null | original basic | 126/200 | 117/126 | 6 | 3 |

bounded_null, original: причины недоступности — {'too few finite bootstrap fits': 62, 'failure_excesses below 50; too few finite bootstrap fits': 12}.
| bounded_null | observed_support percentile | 126/200 | 119/126 | 6 | 1 |
| bounded_null | observed_support basic | 126/200 | 117/126 | 6 | 3 |

bounded_null, observed_support: причины недоступности — {'too few finite bootstrap fits': 62, 'failure_excesses below 50; too few finite bootstrap fits': 12}.

Полная разбивка по положению порога относительно известной границы поддержки, смещению и парным исходам находится в metrics.json. Эта разбивка описательная: её нельзя выдавать за новую независимую валидацию.
Кандидат нельзя продвигать только по условному покрытию; нужно учитывать недоступные интервалы и общую парную выборку.
