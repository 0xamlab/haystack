#!/usr/bin/env bash
set -uo pipefail
cd ~/gemma3_src
export PYTHONPATH=packages/algenta
python3 -c "
from algenta.inference import prepare_model_checkpoint
out = prepare_model_checkpoint('/home/angel/models/gemma-3-27b-it', [2,1756,3402,762], out_dir='/tmp/g3conv27b', weights_dtype='f32')
print('converted ->', out)
import json, os
cfg=json.load(open('/tmp/g3conv27b/manifest.json'))['config']
print('hidden',cfg['hidden_size'],'layers',cfg['num_hidden_layers'],'h_q',cfg['num_attention_heads'],'h_kv',cfg['num_key_value_heads'],'d_head',cfg['head_dim'],'d_ff',cfg['intermediate_size'],'vocab',cfg['vocab_size'])
print('dtype',cfg.get('weights_dtype'),'tied',cfg['tie_word_embeddings'],'qknorm',cfg['has_qk_norm'],'full layers',sum(cfg['layer_types']),'of',len(cfg['layer_types']))
print('blob GB', round(os.path.getsize('/tmp/g3conv27b/weights.blob')/1e9,2))
" 2>&1
echo "CONVERT27B_EXIT=$?"
