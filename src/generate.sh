python create_config.py \
    --profile hv_consep\
    --id 1.0 \
    --input_prefix /data/input/ \
    --output_prefix /data/output/ \
    --preproc \
    --norm_brightness \
    --mode train \
    --image train_1 \
    --extract \
    --export \
    --extract_type mirror \
    --step_size 80 \
    --win_size 540 \
    --input_norm \
    --input_augs p_standard \
    --data_modes train,test \
    --inf_model hv_class_consep.npz \
    --remap_labels \
    --outline ''

# --inf_auto_find_chkpt \
# --inf_model hv_class_consep.npz \