# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/124_models.TSTransformerPlus.ipynb (unless otherwise specified).

__all__ = ['TSTransformerPlus']

# Cell
from ..imports import *
from .layers import *
from typing import Callable

# Cell

class _TSTransformerBackbone(Module):
    def __init__(self, c_in:int, seq_len:int, n_layers:int=3, d_model:int=128, n_heads:int=16, d_head:Optional[int]=None, act:str='reglu',
                 d_ff:int=256, attn_dropout:float=0., fc_dropout:float=0., res_attention:bool=True, pre_norm:bool=False,
                 random_steps:bool=True, use_cls_token:bool=True):

        self.res_attention, self.pre_norm, self.random_steps = res_attention, pre_norm, random_steps

        self.lin = nn.Linear(c_in, d_model)
        self.pos_emb = nn.Parameter(torch.zeros(1, seq_len, d_model))
        self.cls_token = nn.Parameter(torch.zeros(1, 1, d_model)) if use_cls_token else None

        self.layers = nn.ModuleList([])
        for _ in range(n_layers):
            self.layers.append(nn.ModuleList([
                MultiheadAttention(d_model, n_heads, res_attention=res_attention, dropout=attn_dropout),
                nn.LayerNorm(d_model),
                PositionwiseFeedForward(d_model, dropout=fc_dropout, act=act),
                nn.LayerNorm(d_model),
            ]))

    def forward(self, x):

        x = self.lin(x.transpose(1,2))
        x += self.pos_emb

        if self.training and self.random_steps:
            idxs = np.random.choice(x.shape[1], x.shape[1], True)
            x = x[:, idxs]

        if self.cls_token is not None:
            x = torch.cat((self.cls_token.repeat(x.shape[0], 1, 1), x), dim=1)

        for i, (mha, attn_norm, pwff, ff_norm) in enumerate(self.layers):

            # Multi-head attention
            residual = x
            if self.pre_norm: x = attn_norm(x)
            if self.res_attention: x, _, prev = mha(x, x, x, prev=(None if i == 0 else prev))
            else: x, _ = mha(x, x, x)
            x += residual
            del residual
            if not self.pre_norm: x = attn_norm(x)

            # Position-wise feed forward
            if self.pre_norm: x = pwff(ff_norm(x)) + x
            else: x = ff_norm(pwff(x) + x)

        return x


class TSTransformerPlus(nn.Sequential):
    def __init__(self, c_in:int, c_out:int, seq_len:int, n_layers:int=3, d_model:int=128, n_heads:int=16, d_head:Optional[int]=None, act:str='reglu',
                 d_ff:int=256, attn_dropout:float=0., fc_dropout:float=0., res_attention:bool=True, pre_norm:bool=False, use_cls_token:bool=True,
                 random_steps:bool=True, custom_head:Optional[Callable]=None):

        backbone = _TSTransformerBackbone(c_in, seq_len, n_layers=n_layers, d_model=d_model, n_heads=n_heads, d_head=d_head, act=act,
                                          d_ff=d_ff, attn_dropout=attn_dropout, fc_dropout=fc_dropout, res_attention=res_attention,
                                          pre_norm=pre_norm, random_steps=random_steps, use_cls_token=use_cls_token)

        self.head_nf = d_model
        self.c_out = c_out
        self.seq_len = seq_len
        if custom_head: head = custom_head(self.head_nf, c_out, self.seq_len) # custom head passed as a partial func with all its kwargs
        else: head = nn.Sequential(TokenLayer(token=use_cls_token), nn.BatchNorm1d(d_model), nn.Linear(d_model, c_out))
        super().__init__(OrderedDict([('backbone', backbone), ('head', head)]))