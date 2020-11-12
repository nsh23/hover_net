export H_PROFILE=hv_consep

python create_config.py \
    --profile $H_PROFILE \
    --model_type np_hv \
    --id 1.0 \
    --input_prefix /data/input/ \
    --output_prefix /data/output/ \
    --data_dir data_hv_consep/ \
    --train_dir train/Annotations \
    --valid_dir test/Annotations \
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
    --input_augs p_linear \
    --data_modes train,test \
    --inf_auto_find_chkpt \
    --inf_data_list data_hv_consep/test/Images/ \
    --remap_labels \
    --outline ''

# --inf_auto_find_chkpt \
# --inf_model dm_hv_class_consep.npz \