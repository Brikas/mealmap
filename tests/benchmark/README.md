# Benchmarks

This directory holds the performance benchmarks for our project, ensuring that we maintain optimal performance and catch any potential regressions.

## Purpose:

- **Catch Regressions**: As software evolves, unwanted performance degradations might creep in. Regular benchmarking helps to spot these early.
  
- **Optimize Effectively**: When attempting to optimize code, benchmarks provide concrete data to validate if the changes bring the expected improvements.

- **Documentation & Transparency**: Sharing benchmarks provides users and contributors clarity on the software's performance characteristics.

## Process:

1. **Running Benchmarks**: Benchmarks are automatically run in our CI environment on every significant push. The results are saved as artifacts.

2. **Analyzing Results**: To analyze the performance over time, download the artifacts and place them in the same directory as the `analyze_benchmarks.py` script. Then, run the script to visualize the results:

   ```bash
   python analyze_benchmarks.py
   ```

## Candidates

```
├── benchmarks/
│   ├── db/
│   │   ├── benchmark_db_read.py
│   │   ├── benchmark_db_write.py
│   │   └── data/
│   │       ├── input_data.csv
│   │       └── expected_output.csv
│   ├── ml/
│   │   ├── benchmark_model_inference.py
│   │   ├── benchmark_model_training.py
│   │   └── models/
│   │       └── pretrained_model.pkl
│   ├── api/
│   │   ├── benchmark_api_response_time.py
│   │   └── benchmark_api_throughput.py
│   ├── results/
│   │   ├── db_results.csv
│   │   ├── ml_results.csv
│   │   └── api_results.csv
│   ├── utils/
│   │   ├── fetch_from_github.py
│   │   └── visualization.py
```
