#!/bin/bash
#SBATCH --job-name=msconvert
#SBATCH --partition=amd_serial
#SBATCH --nodes=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=08:00:00
#SBATCH --output=/home/cle1g21/RPC/msconvert/logs/msconvert_%j.out
#SBATCH --error=/home/cle1g21/RPC/msconvert/logs/msconvert_%j.err

# Reusable Slurm job script for convert_ms.py on Iridis.
#
# Submit with defaults (Control4 input, mgf output):
#   sbatch /home/cle1g21/RPC/msconvert/run_convert_ms.sh
#
# Submit with custom input/format:
#   INPUT=/path/to/sample.d FORMAT=mgf sbatch /home/cle1g21/RPC/msconvert/run_convert_ms.sh
#   INPUT=/path/to/sample.d FORMAT=mzml OUTPUT_DIR=/path/to/out sbatch /home/cle1g21/RPC/msconvert/run_convert_ms.sh

set -eo pipefail

INPUT="${INPUT:-/home/cle1g21/RPC/msconvert/input_data/Control4_Neo_SN_114_HLA-I.d}"
OUTPUT_DIR="${OUTPUT_DIR:-/home/cle1g21/RPC/msconvert/output_data}"
FORMAT="${FORMAT:-mgf}"
IMAGE="${IMAGE:-/home/cle1g21/RPC/msconvert/proteowizard.sif}"
SCRIPT="${SCRIPT:-/home/cle1g21/RPC/msconvert/convert_ms.py}"

mkdir -p /home/cle1g21/RPC/msconvert/logs
mkdir -p "${OUTPUT_DIR}"

module load apptainer/1.5.0

echo "=== MSConvert job ==="
echo "Job ID:    ${SLURM_JOB_ID:-local}"
echo "Node:      $(hostname)"
echo "Start:     $(date)"
echo "Input:     ${INPUT}"
echo "Output:    ${OUTPUT_DIR}"
echo "Format:    ${FORMAT}"
echo "Image:     ${IMAGE}"
echo ""

python "${SCRIPT}" \
  --input "${INPUT}" \
  --output-dir "${OUTPUT_DIR}" \
  --format "${FORMAT}" \
  --image "${IMAGE}"

echo ""
echo "End:       $(date)"
echo "=== Done ==="
