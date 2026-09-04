# Использование scRNA-seq Agentic Pipeline v1.1.0

## 1. Назначение

Конвейер выполняет 12 стадий интегративного анализа scRNA-seq: от проверки FASTQ и STARsolo до RNA-derived вариантов, gene-burden признаков, ML-валидации, cellSNP, корреляции и сборки отчётных материалов.

RNA-derived варианты не являются подтверждёнными соматическими вариантами без ортогональной проверки по DNA-seq. Результаты ML на малой внутренней выборке не являются клинически валидированным классификатором.

## 2. Системные требования

Рекомендуемая среда для Windows:

- Windows 10/11 и WSL2 с Ubuntu;
- не менее 32 ГБ RAM для полного индекса GRCh38;
- не менее 1 ТБ свободного места для полного набора FASTQ/BAM/VCF;
- Python 3, STAR, samtools, GATK 4 и cellsnp-lite;
- стабильное интернет-соединение при автоматической установке отсутствующих компонентов.

Проверка WSL:

```powershell
wsl.exe --status
wsl.exe -e bash -lc "python3 --version; STAR --version; samtools --version; gatk --version; cellsnp-lite --help | head"
```

## 3. Подготовка данных

Поместите FASTQ в `data/fastq/`.

Для схемы `two_read`:

```text
SAMPLE_R1.fastq.gz  # barcode + UMI
SAMPLE_R2.fastq.gz  # cDNA
```

Для схемы `three_read`:

```text
SAMPLE_R1.fastq.gz  # cDNA
SAMPLE_R2.fastq.gz  # cell barcode
SAMPLE_R3.fastq.gz  # UMI
```

Создайте `data/metadata/metadata.tsv`:

```tsv
sample_id	condition	run_id	sample_title	gsm
SRR000001	unwounded	SRR000001	Sample_1	GSM000001
SRR000002	wound	SRR000002	Sample_2	GSM000002
```

Обязательные поля: `sample_id`, `condition`, `run_id`. Для групповой ML-валидации также нужен `gsm` или другой идентификатор независимой биологической группы.

## 4. Подготовка референсов

Необходимо предоставить:

```text
config/ref/genome.fa
config/ref/genome.fa.fai
config/ref/genes.gtf
config/ref/STAR_index/
config/ref/whitelist.txt
```

Пути и параметры химии задаются в:

- `config/starsolo_config.json`;
- `config/gatk_config.json`;
- остальных JSON-файлах каталога `config/`.

Перед запуском обязательно проверьте соответствие `CBlen`, `UMIlen`, порядка R1/R2/R3 и whitelist фактической библиотечной химии.

## 5. Полный автоматический запуск

Из PowerShell в корне репозитория:

```powershell
.\zapusti_analiz.ps1
```

Эквивалентная команда:

```powershell
python scripts/run_agentic_pipeline.py --auto-install --start-status --use-wsl
```

Упрощённый последовательный runner:

```powershell
python scripts/run_autonomous_pipeline.py --auto-install --start-status --use-wsl
```

Flask-интерфейс после запуска:

```text
http://127.0.0.1:5556
```

## 6. Запуск диапазона стадий

```powershell
python scripts/run_autonomous_pipeline.py --use-wsl --from-stage 01_input_data --end-stage 03_gatk_call
```

Для продолжения с конкретной стадии:

```powershell
python scripts/run_autonomous_pipeline.py --use-wsl --from-stage 04_cohort_filter
```

Перед продолжением убедитесь, что предыдущая стадия создала проверенные артефакты. Частичный запуск сейчас сбрасывает отображаемую историю статусов Flask, но не удаляет научные артефакты.

## 7. Лёгкий smoke-test на одной паре R1/R2

Один образец подходит для технической проверки стадий FASTQ → STARsolo → GATK → variant-to-gene → gene burden → cellSNP. Он не подходит для классификации двух условий и корреляционного анализа.

Минимальный metadata-файл:

```tsv
sample_id	condition	run_id	sample_title	gsm
SMOKE001	unwounded	SMOKE001	Smoke_sample	SMOKE_GROUP
```

Запуск первых стадий:

```powershell
python scripts/run_autonomous_pipeline.py --use-wsl --from-stage 01_input_data --end-stage 03_gatk_call
```

Для технической проверки cohort-фильтра на одном образце временно используйте отдельную smoke-конфигурацию с `min_samples: 1`. Не заменяйте этим значением основной исследовательский порог.

Ожидаемый результат для стадий 07 и 11 при одном образце — `NOT_APPLICABLE`, а не научная метрика.

## 8. Основные артефакты

- Stage 01: очищенный metadata TSV и таблица входных образцов.
- Stage 02: BAM, BAI, `Solo.out/Gene/raw` и `Solo.out/Gene/filtered`.
- Stage 03: raw, filtered-with-filters и PASS VCF.
- Stages 04–06: cohort VCF, variant–gene таблица и gene-burden матрица.
- Stage 07: ML-метрики, групповые предсказания и permutation test.
- Stages 08–10: cellSNP, cluster counts и мутационные сводки.
- Stage 11: интеграционная таблица, корреляции и графики.
- Stage 12: `for_report/` и manifest собранных файлов.

## 9. Проверка корректности

Минимальная ручная проверка BAM:

```powershell
wsl.exe -e bash -lc "samtools quickcheck -v PATH/TO/Aligned.sortedByCoord.out.bam"
```

Команда должна завершиться с кодом `0`. Наличие файла без проверки содержимого не считается успешной стадией.

Проверяйте для каждой стадии:

1. код завершения;
2. наличие и ненулевой размер обязательных файлов;
3. внутреннюю валидность формата;
4. согласованность идентификатора образца;
5. статус и журнал в Flask;
6. допустимость перехода к следующей стадии.

## 10. Границы интерпретации

- SRR-запуски одного GSM не считаются независимыми биологическими наблюдениями.
- Основная проверка переносимости внутри набора должна учитывать GSM-группы.
- Формирование признаков выполняется только на обучающих данных соответствующего fold.
- RNA-derived варианты требуют осторожной интерпретации и DNA-подтверждения.
- Для клинических выводов необходима независимая внешняя когорта.
