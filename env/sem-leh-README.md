The way I got the env for sem-leh2 to work (sem-leh2 is a clean install from zero) was:

1. Install the env from the environment-gpu-leh.yml file (including the pip package)
2. Manually install spacy
3. Install the deps from the evaluation harness + the extensions for more tasks
4. I had to remove click and reinstall it bc it lead to weird issues. Once I completely removed it and installed it with mamba, it worked fine


The result is also dumped into the file sem-leh-reworked.yml.
Can try to recreate it by using it and then installing pip installs from the eval harness.