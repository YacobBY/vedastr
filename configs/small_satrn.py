# work dir
root_workdir = 'workdir/'

# seed
seed = 1111

# 1. logging
logger = dict(
    handlers=(
        dict(type='StreamHandler', level='INFO'),
        dict(type='FileHandler', level='INFO'),
    ),
)

# 2. data
batch_size = 256
mean, std = 0.5, 0.5  # normalize mean and std
size = (32, 100)
batch_max_length = 25
fill = 0
mode = 'nearest'
data_filter_off = False
train_sensitive = True
train_character = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~'  # need character
test_sensitive = False
test_character = '0123456789abcdefghijklmnopqrstuvwxyz'

# dataset params
train_dataset_params = dict(
    batch_max_length=batch_max_length,
    data_filter_off=data_filter_off,
    character=train_character,
)
test_dataset_params = dict(
    batch_max_length=batch_max_length,
    data_filter_off=data_filter_off,
    character=test_character,
)

data_root = './data/data_lmdb_release/'

# train data
train_root = data_root + 'training/'
## MJ dataset
train_root_mj = train_root + 'MJ/'
mj_folder_names = ['/MJ_test', 'MJ_valid', 'MJ_train']
## ST dataset
train_root_st = train_root + 'ST/'

train_dataset_mj = [dict(type='LmdbDataset', root=train_root_mj + folder_name) for folder_name in mj_folder_names]
train_dataset_st = [dict(type='LmdbDataset', root=train_root_st)]

# valid
valid_root = data_root + 'validation/'
valid_dataset = [dict(type='LmdbDataset', root=valid_root, **test_dataset_params)]

# test
test_root = data_root + 'evaluation/'
test_folder_names = ['CUTE80', 'IC03_867', 'IC13_1015', 'IC15_2077', 'IIIT5k_3000', 'SVT', 'SVTP']
test_dataset = [dict(type='LmdbDataset', root=test_root + folder_name, **test_dataset_params) for folder_name in
                test_folder_names]

# transforms
train_transforms = [
    dict(type='Sensitive', sensitive=train_sensitive),
    dict(type='ColorToGray'),
    dict(type='RandomNormalRotation', mean=0, std=34, expand=True, center=None, fill=fill, mode=mode, p=0.5),
    dict(type='Resize', size=size),
    dict(type='ToTensor'),
    dict(type='Normalize', mean=mean, std=std),
]
test_transforms = [
    dict(type='Sensitive', sensitive=test_sensitive),
    dict(type='ColorToGray'),
    dict(type='Resize', size=size),
    dict(type='ToTensor'),
    dict(type='Normalize', mean=mean, std=std),
]

data = dict(
    train=dict(
        transforms=train_transforms,
        datasets=[
            dict(
                type='ConcatDatasets',
                datasets=train_dataset_mj,
                **train_dataset_params,
            ),
            dict(
                type='ConcatDatasets',
                datasets=train_dataset_st,
                **train_dataset_params,
            ),
        ],
        loader=dict(
            type='BatchBalanceDataloader',
            batch_size=batch_size,
            each_batch_ratio=[0.5, 0.5],
            each_usage=[1.0, 1.0],
            shuffle=True,
            num_workers=4,
        ),
    ),
    val=dict(
        transforms=test_transforms,
        datasets=valid_dataset,
        loader=dict(
            type='TestDataloader',
            batch_size=batch_size,
            num_workers=4,
            shuffle=False,
        ),
    ),
    test=dict(
        transforms=test_transforms,
        datasets=test_dataset,
        loader=dict(
            type='TestDataloader',
            batch_size=batch_size,
            num_workers=4,
            shuffle=False,
        ),
    ),
)

test_cfg = dict(
    sensitive=test_sensitive,
    character=test_character,
)

# 3. converter
converter = dict(
    type='SATRNConverter',
    character=train_character,
    batch_max_length=batch_max_length,
    go_last=True,
)

# 4. model
dropout = 0.1
n_e = 9
n_d = 3
hidden_dim = 256
n_head = 8
batch_norm = dict(type='BN')
layer_norm = dict(type='LayerNorm', normalized_shape=hidden_dim)
num_class = len(train_character) + 1
num_steps = batch_max_length + 1
model = dict(
    type='GModel',
    need_text=True,
    body=dict(
        type='GBody',
        pipelines=[
            dict(
                type='FeatureExtractorComponent',
                from_layer='input',
                to_layer='cnn_feat',
                arch=dict(
                    encoder=dict(
                        backbone=dict(
                            type='GResNet',
                            layers=[
                                ('conv',
                                 dict(type='ConvModule', in_channels=1, out_channels=int(hidden_dim / 2), kernel_size=3,
                                      stride=1, padding=1, norm_cfg=batch_norm)),
                                ('pool', dict(type='MaxPool2d', kernel_size=2, stride=2, padding=0)),
                                ('conv',
                                 dict(type='ConvModule', in_channels=int(hidden_dim / 2), out_channels=hidden_dim,
                                      kernel_size=3,
                                      stride=1, padding=1, norm_cfg=batch_norm)),
                                ('pool', dict(type='MaxPool2d', kernel_size=2, stride=2, padding=0)),
                            ],
                        ),
                    ),
                    collect=dict(type='CollectBlock', from_layer='c2'),
                ),
            ),
            dict(
                type='SequenceEncoderComponent',
                from_layer='cnn_feat',
                to_layer='src',
                arch=dict(
                    type='TransformerEncoder',
                    position_encoder=dict(
                        type='Adaptive2DPositionEncoder',
                        in_channels=hidden_dim,
                        max_h=100,
                        max_w=100,
                        dropout=dropout,
                    ),
                    encoder_layer=dict(
                        type='TransformerEncoderLayer2D',
                        attention=dict(
                            type='MultiHeadAttention',
                            in_channels=hidden_dim,
                            k_channels=hidden_dim,
                            v_channels=hidden_dim,
                            n_head=n_head,
                            dropout=dropout,
                        ),
                        attention_norm=layer_norm,
                        feedforward=dict(
                            type='Feedforward',
                            layers=[
                                dict(type='ConvModule', in_channels=hidden_dim, out_channels=hidden_dim * 4,
                                     kernel_size=3, padding=1,
                                     bias=True, norm_cfg=None, activation='relu', dropout=dropout),
                                dict(type='ConvModule', in_channels=hidden_dim * 4, out_channels=hidden_dim,
                                     kernel_size=3, padding=1,
                                     bias=True, norm_cfg=None, activation=None, dropout=dropout),
                            ],
                        ),
                        feedforward_norm=layer_norm,
                    ),
                    num_layers=n_e,
                ),
            ),
        ],
    ),
    head=dict(
        type='TransformerHead',
        src_from='src',
        num_steps=num_steps,
        pad_id=num_class,
        decoder=dict(
            type='TransformerDecoder',
            position_encoder=dict(
                type='PositionEncoder1D',
                in_channels=hidden_dim,
                max_len=100,
                dropout=dropout,
            ),
            decoder_layer=dict(
                type='TransformerDecoderLayer1D',
                self_attention=dict(
                    type='MultiHeadAttention',
                    in_channels=hidden_dim,
                    k_channels=hidden_dim,
                    v_channels=hidden_dim,
                    n_head=n_head,
                    dropout=dropout,
                ),
                self_attention_norm=layer_norm,
                attention=dict(
                    type='MultiHeadAttention',
                    in_channels=hidden_dim,
                    k_channels=hidden_dim,
                    v_channels=hidden_dim,
                    n_head=n_head,
                    dropout=dropout,
                ),
                attention_norm=layer_norm,
                feedforward=dict(
                    type='Feedforward',
                    layers=[
                        dict(type='FCModule', in_channels=hidden_dim, out_channels=hidden_dim * 4, bias=True,
                             activation='relu', dropout=dropout),
                        dict(type='FCModule', in_channels=hidden_dim * 4, out_channels=hidden_dim, bias=True,
                             activation=None, dropout=dropout),
                    ],
                ),
                feedforward_norm=layer_norm,
            ),
            num_layers=n_d,
        ),
        generator=dict(
            type='Linear',
            in_features=hidden_dim,
            out_features=num_class,
        ),
        embedding=dict(
            type='Embedding',
            num_embeddings=num_class + 1,
            embedding_dim=hidden_dim,
            padding_idx=num_class,
        ),
    ),
)

## 4.1 resume
resume = None

# 5. criterion
criterion = dict(type='CrossEntropyLoss', ignore_index=num_class)

# 6. optim
optimizer = dict(type='Adam', lr=1e-4)

# 7. lr scheduler
epochs = 6
milestones = [2, 4]
niter_per_epoch = int(55000 * 256 / batch_size)
max_iterations = epochs * niter_per_epoch
milestones = [niter_per_epoch * epoch for epoch in milestones]
lr_scheduler = dict(type='StepLR',
                    niter_per_epoch=niter_per_epoch,
                    max_epochs=epochs,
                    milestones=milestones,
                    gamma=0.1,
                    warmup_epochs=0.1,
                    )

# 8. runner
runner = dict(
    type='Runner',
    iterations=max_iterations,
    trainval_ratio=2000,
    snapshot_interval=20000,
)

# 9. device
gpu_id = '3'
