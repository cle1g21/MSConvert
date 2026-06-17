# MSConvert Pipeline (Apptainer on Iridis HPC)

This folder contains a repeatable pipeline to convert vendor mass spectrometry raw files (for example Bruker `.d` folders or Thermo `.raw` files) into open formats: **MGF** (default) or **mzML**.

**Default format is MGF** because `.mgf` files are typically much smaller than `.mzML`, which saves disk space and speeds up downstream tools like InstaNovo.

The pipeline runs **ProteoWizard MSConvert** inside an **Apptainer** container. Apptainer is the production container runtime on the Iridis cluster. You do not need Docker or root access.

---

## Overview

| What | Explanation |
|------|-------------|
| **Input** | Any supported vendor raw file or folder you pass with `--input` |
| **Output** | A `.mgf` or `.mzML` file written to the directory you pass with `--output-dir` (default format: **mgf**) |
| **How** | `convert_ms.py` calls `apptainer run` with bind mounts so MSConvert can read your data and write results back to the host |
| **Why Apptainer** | Iridis provides Apptainer via environment modules. It runs unprivileged and is designed for shared HPC systems |

The ProteoWizard software is distributed as a Docker image on Docker Hub. On Iridis we **pull that image once** with Apptainer and save it as a local `.sif` file. After that, all conversions use the local image.

**Vendor license:** The image name includes `i-agree-to-the-vendor-licenses`. Using it means you agree to the [ProteoWizard vendor licenses](http://proteowizard.sourceforge.net/licenses.html).

---

## Prerequisites

Before you start, make sure you have:

1. **Apptainer module loaded** (required every new terminal session):

   ```bash
   module load apptainer/1.5.0
   ```

   - **What it does:** Adds the cluster Apptainer program to your `PATH`.
   - **If you skip it:** Commands like `apptainer` and `convert_ms.py` will fail with "command not found".

2. **Local Apptainer image** (`proteowizard.sif`) — see [One-time image pull](#one-time-image-pull) below.

3. **Disk space:** About 2 GB for the image, plus space for input and output files.

4. **Network** (login node only, for the one-time image pull).

---

## Directory layout

```
/home/cle1g21/RPC/msconvert/
├── convert_ms.py          ← Python automation script
├── run_convert_ms.sh      ← Reusable Slurm job submission script
├── proteowizard.sif       ← Apptainer image (created by apptainer pull)
├── README.md              ← This file
├── logs/                  ← Slurm job stdout/stderr (created on submit)
├── input_data/            ← Optional staging area for raw files
│   └── (your .d / .raw / .wiff files)
└── output_data/           ← Default output directory (--output-dir)
    └── (converted .mgf or .mzML files appear here)
```

`input_data/` is convenient but **not required**. You can pass any path to `--input` on the filesystem.

---

## One-time image pull

**Command name:** `apptainer pull`

**Core purpose:** Download the ProteoWizard Docker image from Docker Hub and save it as a local Apptainer `.sif` file on the host.

**Input parameters:**

| Part | Meaning |
|------|---------|
| `module load apptainer/1.5.0` | Activate Apptainer on the cluster |
| `export APPTAINER_CACHEDIR=...` | Optional: where Apptainer stores download cache |
| `apptainer pull <local.sif>` | Write the image to this path on the host |
| `docker://proteowizard/pwiz-skyline-i-agree-to-the-vendor-licenses` | Remote image location (Docker Hub URI) |

**Commands:**

```bash
module load apptainer/1.5.0

export APPTAINER_CACHEDIR=/home/cle1g21/.apptainer/cache
mkdir -p "$APPTAINER_CACHEDIR"

apptainer pull /home/cle1g21/RPC/msconvert/proteowizard.sif \
  docker://proteowizard/pwiz-skyline-i-agree-to-the-vendor-licenses
```

**Return outputs:**

- File: `/home/cle1g21/RPC/msconvert/proteowizard.sif` (about 1.6–2.2 GB)
- Terminal log lines showing download and SIF creation progress

**Code walkthrough:** Apptainer contacts Docker Hub, downloads the image layers, converts them to a single `.sif` file on the host. All later conversion runs read this local file — no network needed per conversion.

---

## Apptainer command-line mirroring

This section shows the exact command structure that `convert_ms.py` builds. Replace the example variables with your own paths and filenames.

### Step 1: Load the module

```bash
module load apptainer/1.5.0
```

### Step 2: Set paths (example)

```bash
INPUT_PARENT="/home/cle1g21/RPC/msconvert/input_data"
INPUT_NAME="Control4_Neo_SN_114_HLA-I.d"
OUTPUT_DIR="/home/cle1g21/RPC/msconvert/output_data"
```

- `INPUT_PARENT` = directory on the **host** that **contains** your raw file
- `INPUT_NAME` = filename or folder name only (not the full path)
- `OUTPUT_DIR` = directory on the **host** where converted files should appear

### Step 3: Run conversion with `apptainer run`

**MGF example (default format — smaller output files):**

```bash
apptainer run --unsquash \
  --bind "${INPUT_PARENT}:/data_in" \
  --bind "${OUTPUT_DIR}:/data_out" \
  /home/cle1g21/RPC/msconvert/proteowizard.sif \
  wine msconvert "/data_in/${INPUT_NAME}" -o /data_out --mgf
```

**Why `--unsquash`?** On Iridis compute nodes, FUSE-based image mounting (`fusermount`) is often unavailable. The `--unsquash` flag unpacks the `.sif` image to a temporary directory instead, which avoids the mount failure.

**mzML example** (larger files; use when a tool specifically requires mzML):

```bash
apptainer run --unsquash \
  --bind "${INPUT_PARENT}:/data_in" \
  --bind "${OUTPUT_DIR}:/data_out" \
  /home/cle1g21/RPC/msconvert/proteowizard.sif \
  wine msconvert "/data_in/${INPUT_NAME}" -o /data_out --mzML
```

**MGF example** (same command, different format flag):

```bash
apptainer run --unsquash \
  --bind "${INPUT_PARENT}:/data_in" \
  --bind "${OUTPUT_DIR}:/data_out" \
  /home/cle1g21/RPC/msconvert/proteowizard.sif \
  wine msconvert "/data_in/${INPUT_NAME}" -o /data_out --mgf
```

**Short-form bind syntax** (`-B` is identical to `--bind`):

```bash
apptainer run --unsquash \
  -B "${INPUT_PARENT}:/data_in" \
  -B "${OUTPUT_DIR}:/data_out" \
  /home/cle1g21/RPC/msconvert/proteowizard.sif \
  wine msconvert "/data_in/${INPUT_NAME}" -o /data_out --mzML
```

### Optional: `apptainer exec` (advanced)

Same bind mounts and MSConvert arguments; useful when you want to run a single command inside an existing image context:

```bash
apptainer exec --unsquash \
  --bind "${INPUT_PARENT}:/data_in" \
  --bind "${OUTPUT_DIR}:/data_out" \
  /home/cle1g21/RPC/msconvert/proteowizard.sif \
  wine msconvert "/data_in/${INPUT_NAME}" -o /data_out --mzML
```

`convert_ms.py` uses **`apptainer run`** (the standard one-shot invocation).

---

## Bind-mount mapping (host ↔ container)

Apptainer runs in an isolated filesystem. **Bind mounts** connect real host directories to paths inside the image.

| Host (real) path | Apptainer flag | Path inside image | What happens |
|------------------|----------------|-------------------|--------------|
| Parent directory of your `--input` file | `--bind <parent>:/data_in` | `/data_in` | Your raw file is visible inside the image as `/data_in/<basename>`. MSConvert reads it from there. |
| Your `--output-dir` directory | `--bind <output_dir>:/data_out` | `/data_out` | MSConvert writes converted files here inside the image. They appear immediately on the host at the same path. |

**Example** with `Control4_Neo_SN_114_HLA-I.d`:

| Host | Inside image |
|------|--------------|
| `/home/cle1g21/RPC/msconvert/input_data/Control4_Neo_SN_114_HLA-I.d` | `/data_in/Control4_Neo_SN_114_HLA-I.d` |
| `/home/cle1g21/RPC/msconvert/output_data/` | `/data_out/` |

After a successful MGF conversion (default), the output file on the host is:

`/home/cle1g21/RPC/msconvert/output_data/Control4_Neo_SN_114_HLA-I.mgf`

MSConvert names the output from the **input filename stem** (the part before the extension).

---

## Flag and argument reference

| Flag / argument | Where used | Plain-English meaning |
|-----------------|------------|------------------------|
| `module load apptainer/1.5.0` | Terminal (before any run) | Activates the cluster Apptainer binary |
| `apptainer run` | Terminal or script | Start the image and run one command, then exit |
| `apptainer exec` | Terminal (advanced) | Run one command inside the image |
| `apptainer pull` | Terminal (one-time) | Download Docker Hub image as local `.sif` |
| `--unsquash` | `apptainer run` / `exec` | Unpack the `.sif` image instead of FUSE-mounting (required on Iridis) |
| `--bind` / `-B` | `apptainer run` / `exec` | Map `host_path:container_path` |
| `proteowizard.sif` | Command argument | Local Apptainer image file on the host |
| `wine msconvert` | Inside container | Run Windows MSConvert via Wine |
| `/data_in/<name>` | MSConvert argument | Input file path **as seen inside the image** |
| `-o /data_out` | MSConvert argument | Output directory **inside the image** (maps to host `--output-dir`) |
| `--mzML` | MSConvert argument | Write mzML format (use with `--format mzml`) |
| `--mgf` | MSConvert argument | Write MGF format (use with `--format mgf`) |

### Expected output files

| `--format` | MSConvert flag | Example output (input `sample.d`) |
|------------|----------------|-----------------------------------|
| `mzml` | `--mzML` | `<output_dir>/sample.mzML` |
| `mgf` | `--mgf` | `<output_dir>/sample.mgf` |

**Note:** mzML files may use `.mzML` (capital ML). Linux is case-sensitive. The script checks both casings.

---

## Using `convert_ms.py`

### Command-line arguments

| Argument | Required | Default | Purpose |
|----------|----------|---------|---------|
| `--input` | Yes | — | Path to any vendor raw file or folder |
| `--output-dir` | No | `/home/cle1g21/RPC/msconvert/output_data` | Host directory for converted files |
| `--format` | No | `mgf` | `mgf` or `mzml` |
| `--image` | No | `/home/cle1g21/RPC/msconvert/proteowizard.sif` | Path to Apptainer image |

### Examples

**Convert a Bruker `.d` folder to MGF (default — no `--format` needed):**

```bash
module load apptainer/1.5.0

python /home/cle1g21/RPC/msconvert/convert_ms.py \
  --input /home/cle1g21/RPC/msconvert/input_data/Control4_Neo_SN_114_HLA-I.d \
  --output-dir /home/cle1g21/RPC/msconvert/output_data
```

**Convert the same file to mzML (larger output):**

```bash
python /home/cle1g21/RPC/msconvert/convert_ms.py \
  --input /home/cle1g21/RPC/msconvert/input_data/Control4_Neo_SN_114_HLA-I.d \
  --output-dir /home/cle1g21/RPC/msconvert/output_data \
  --format mzml
```

**Convert any file elsewhere on the filesystem:**

```bash
python /home/cle1g21/RPC/msconvert/convert_ms.py \
  --input /path/to/your_run.raw \
  --output-dir /path/to/results
```

### Step-by-step workflow

1. Open a terminal on Iridis.
2. Run `module load apptainer/1.5.0`.
3. Ensure `proteowizard.sif` exists (pull once if needed).
4. Place raw data somewhere readable, or use `input_data/`.
5. Run `convert_ms.py` with `--input`, `--output-dir`, and `--format`.
6. Check the printed **stdout** / **stderr** logs and confirm the output file path and size.


---

## Running as a Slurm job (recommended for long conversions)

MSConvert does **not** need a GPU. Use a **CPU partition** such as `amd_serial`.

### Submit Control4 with default settings (MGF output)

The bundled script `run_convert_ms.sh` defaults to:

- **Input:** `/home/cle1g21/RPC/msconvert/input_data/Control4_Neo_SN_114_HLA-I.d`
- **Output:** `/home/cle1g21/RPC/msconvert/output_data`
- **Format:** `mgf`

```bash
sbatch /home/cle1g21/RPC/msconvert/run_convert_ms.sh
```

Slurm prints a job ID, for example `Submitted batch job 1026500`.

### Monitor the job

```bash
squeue -u $USER
tail -f /home/cle1g21/RPC/msconvert/logs/msconvert_<JOBID>.out
```

### Cancel a job

```bash
scancel <JOBID>
```

### Reuse for other files (environment variables)

Override defaults at submit time without editing the script:

| Variable | Default | Purpose |
|----------|---------|---------|
| `INPUT` | `.../Control4_Neo_SN_114_HLA-I.d` | Path to raw file or folder |
| `OUTPUT_DIR` | `.../output_data` | Host output directory |
| `FORMAT` | `mgf` | `mgf` or `mzml` |
| `IMAGE` | `.../proteowizard.sif` | Apptainer image path |

```bash
INPUT=/path/to/another_sample.d FORMAT=mgf sbatch /home/cle1g21/RPC/msconvert/run_convert_ms.sh

INPUT=/path/to/sample.d FORMAT=mzml OUTPUT_DIR=/path/to/results sbatch /home/cle1g21/RPC/msconvert/run_convert_ms.sh
```

### Slurm resource requests (in `run_convert_ms.sh`)

| Setting | Value | Why |
|---------|-------|-----|
| `--partition=amd_serial` | CPU serial queue | MSConvert is CPU-only (no GPU) |
| `--cpus-per-task=4` | 4 CPUs | Conversion workload |
| `--mem=32G` | 32 GB RAM | Safe headroom for large files |
| `--time=08:00:00` | 8 hours | Large `.d` folders can take hours |

## `convert_ms.py` function reference

Each function below is documented with: **purpose**, **inputs**, **outputs**, and a **walkthrough** of how data moves between host and container.

---

### `parse_command_line_arguments()`

**Core purpose:** Read `--input`, `--output-dir`, `--format`, and `--image` from the command line.

**Input parameters:** None (reads `sys.argv`).

**Return outputs:** An `argparse` namespace object with the user's choices.

**Code walkthrough:** Creates an argument parser, registers the four CLI options, validates `--format` is `mzml` or `mgf`, and returns the parsed values to `main()`.

---

### `resolve_input_paths(input_path)`

**Core purpose:** Convert the user's `--input` into absolute host paths for bind mounts.

**Input parameters:**

| Parameter | Type | Meaning |
|-----------|------|---------|
| `input_path` | `str` | Path the user passed to `--input` |

**Return outputs:** Tuple of `(absolute_input_path, host_input_parent_directory, input_basename)`.

**Code walkthrough:**

1. `os.path.abspath(input_path)` → full host path to the raw file.
2. `os.path.dirname(...)` → parent folder bound to `/data_in`.
3. `os.path.basename(...)` → name passed to MSConvert as `/data_in/<basename>`.

---

### `resolve_output_directory(output_directory)`

**Core purpose:** Resolve `--output-dir` to an absolute host path and create it if missing.

**Input parameters:**

| Parameter | Type | Meaning |
|-----------|------|---------|
| `output_directory` | `str` | User's `--output-dir` value |

**Return outputs:** Absolute path string (host path bound to `/data_out`).

**Code walkthrough:** Absolutizes the path, calls `os.makedirs(..., exist_ok=True)`, returns the path used in `--bind <path>:/data_out`.

---

### `get_input_stem(input_path)` / `get_expected_output_path(...)`

**Core purpose:** Predict the output filename MSConvert will create from the input stem.

**Input parameters:** Input path, output directory, and format (`mzml` or `mgf`).

**Return outputs:** Full expected host path (e.g. `.../sample.mzML`).

**Code walkthrough:** Strips the input extension, appends `.mzML` or `.mgf`, joins with output directory. Used after conversion to verify the file exists.

---

### `check_apptainer_available()`

**Core purpose:** Confirm `apptainer` is on `PATH` (after `module load`).

**Return outputs:** `True` if found; `False` and an error message if not.

**Code walkthrough:** Uses `shutil.which("apptainer")`. On failure, prints `module load apptainer/1.5.0` instructions.

---

### `check_input_exists(absolute_input_path)`

**Core purpose:** Verify the raw file or folder exists before starting the container.

**Return outputs:** `True` if `os.path.exists` succeeds; `False` otherwise.

---

### `check_apptainer_image(image_path)`

**Core purpose:** Verify `proteowizard.sif` exists on the host.

**Return outputs:** `True` if the file exists; `False` with `apptainer pull` instructions if not.

---

### `build_apptainer_command(...)`

**Core purpose:** Build the exact `apptainer run` argument list (mirrors the manual command in this README).

**Input parameters:**

| Parameter | Meaning |
|-----------|---------|
| `host_input_parent_directory` | Host path bound to `/data_in` |
| `input_basename` | Filename inside `/data_in` |
| `host_output_directory` | Host path bound to `/data_out` |
| `image_path` | Path to `.sif` file |
| `msconvert_format_flag` | `--mzML` or `--mgf` |

**Return outputs:** List of strings passed to `subprocess.run` (no shell).

**Code walkthrough:**

1. `apptainer run --unsquash`
2. `--bind <input_parent>:/data_in`
3. `--bind <output_dir>:/data_out`
4. Image path, then `wine msconvert /data_in/<basename> -o /data_out <format_flag>`

---

### `run_conversion(apptainer_command)`

**Core purpose:** Execute the container command and show logs to the user.

**Return outputs:** `subprocess.CompletedProcess` with `returncode`, `stdout`, `stderr`.

**Code walkthrough:** Prints the command, runs `subprocess.run(..., capture_output=True, text=True)`, prints stdout and stderr sections to the terminal.

---

### `verify_output_file(expected_output_path, output_format)`

**Core purpose:** Confirm the converted file exists on the host and report its size.

**Return outputs:** Path to the found file, or `None` if missing.

**Code walkthrough:** For mzML, checks `.mzML` and `.mzml` casings. Prints success message with byte size.

---

### `main()`

**Core purpose:** Orchestrate parse → validate → convert → verify.

**Code walkthrough:**

1. Parse CLI arguments.
2. Resolve input/output paths.
3. Run pre-checks (apptainer, input, image).
4. Build and run Apptainer command.
5. Verify output file; exit `0` on success, `1` on failure.

---

## Log and output file reference

| Output | Type | Meaning |
|--------|------|---------|
| Terminal stdout | Text | MSConvert progress from inside the container |
| Terminal stderr | Text | Wine/MSConvert diagnostics (often verbose; not always an error) |
| `<stem>.mzML` or `<stem>.mgf` | File on host | Converted open-format spectra |
| Exit code `0` | Integer | Success |
| Exit code `1` | Integer | Pre-check, conversion, or verification failed |

---

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| `apptainer: command not found` | Module not loaded | `module load apptainer/1.5.0` |
| `fusermount: No such file or directory` | FUSE mounting unavailable on node | Use `--unsquash` (included automatically in `convert_ms.py`) |
| `Apptainer image not found` | `.sif` not pulled | Run `apptainer pull` (see above) |
| `Input path does not exist` | Wrong `--input` path | Check spelling and `ls` the path |
| Permission denied on output | Cannot write to `--output-dir` | `chmod` or choose a writable directory |
| Long verbose stderr | Normal Wine output | Ignore unless exit code is non-zero |
| Output file not found | Case mismatch (`.mzML` vs `.mzml`) | Script checks both; look in `--output-dir` manually |
| Pull fails on compute node | No network on compute nodes | Run `apptainer pull` on the login node |

Optional debug for Wine issues:

```bash
export WINEDEBUG=fixme-all+msgbox+relay
```

---

## Downstream use

The [InstaNovo](https://github.com/cle1g21/instanovo/) project in this workspace accepts both **`.mgf`** and **`.mzML`** files as input for de novo peptide sequencing.

Example after conversion:

```bash
instanovo predict --data-path /home/cle1g21/RPC/msconvert/output_data/YourFile.mgf --output-path predictions.csv
```

---

## Quick reference card

```bash
# Every new session:
module load apptainer/1.5.0

# Convert any file (MGF is default):
python /home/cle1g21/RPC/msconvert/convert_ms.py \
  --input /path/to/raw/file_or_folder \
  --output-dir /path/to/output

# Submit as Slurm job (Control4 input, MGF output):
sbatch /home/cle1g21/RPC/msconvert/run_convert_ms.sh

# Custom input via environment variables:
INPUT=/path/to/sample.d FORMAT=mgf sbatch /home/cle1g21/RPC/msconvert/run_convert_ms.sh
```
