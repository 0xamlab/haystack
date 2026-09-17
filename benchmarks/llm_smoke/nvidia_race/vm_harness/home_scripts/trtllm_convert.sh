#!/bin/bash
# Task C prep: build the algenta f32 checkpoint blob into a RAM-backed tmpfs
# (root disk has only ~112G free; the blob is ~108GB; VM has 2.9TB RAM).
# Does NOT modify ~/gemma3_src (repo) — mirrors ~/convert_27b.sh with a tmpfs out_dir.
exec > /home/angel/trtllm/convert.log 2>&1
set -x
date -u
echo "=== sudo check ==="
sudo -n true && echo "sudo_ok" || echo "sudo_MISSING"
echo "=== tmpfs mount ==="
sudo -n mkdir -p /mnt/ramblob
sudo -n mount -t tmpfs -o size=220G tmpfs /mnt/ramblob
mount | grep ramblob
sudo -n chown angel:angel /mnt/ramblob
df -h /mnt/ramblob
mkdir -p /mnt/ramblob/g3conv27b
echo "=== convert (f32 blob, out_dir=/mnt/ramblob/g3conv27b) ==="
cd /home/angel/gemma3_src || exit 1
export PYTHONPATH=packages/algenta
time python3 -c "
from algenta.inference import prepare_model_checkpoint
out = prepare_model_checkpoint('/home/angel/models/gemma-3-27b-it', [2,1756,3402,762], out_dir='/mnt/ramblob/g3conv27b', weights_dtype='f32')
print('converted ->', out)
import json, os
cfg=json.load(open('/mnt/ramblob/g3conv27b/manifest.json'))['config']
print('hidden',cfg['hidden_size'],'layers',cfg['num_hidden_layers'],'h_q',cfg['num_attention_heads'],'h_kv',cfg['num_key_value_heads'],'d_head',cfg['head_dim'],'d_ff',cfg['intermediate_size'],'vocab',cfg['vocab_size'])
print('dtype',cfg.get('weights_dtype'),'tied',cfg['tie_word_embeddings'],'qknorm',cfg['has_qk_norm'],'full layers',sum(cfg['layer_types']),'of',len(cfg['layer_types']))
print('blob GB', round(os.path.getsize('/mnt/ramblob/g3conv27b/weights.blob')/1e9,2))
"
echo "CONVERT_EXIT=$?"
date -u
ls -la /mnt/ramblob/g3conv27b
df -h /mnt/ramblob /
free -g | head -2
echo "=== DONE ==="
