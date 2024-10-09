# Orig v001 changed to v002 main flow and signatures
# Back from SiLU to LeakyReLU to test data flow
# Warps moved to flownet forward
# Different Tail from flownet 2lh (ConvTr 6x6, conv 1x1, ConvTr 4x4, conv 1x1)

class Model:

    info = {
        'name': 'Flownet4_v001eb_dv01',
        'file': 'flownet4_v001eb_dv01.py',
        'padding': 128,
        'ratio_support': True
    }

    def __init__(self, status = dict(), torch = None):
        if torch is None:
            import torch
        Module = torch.nn.Module
        backwarp_tenGrid = {}

        def conv(in_planes, out_planes, kernel_size=3, stride=1, padding=1, dilation=1):
            return torch.nn.Sequential(
                torch.nn.Conv2d(
                    in_planes, 
                    out_planes, 
                    kernel_size=kernel_size, 
                    stride=stride,
                    padding=padding, 
                    dilation=dilation,
                    padding_mode='zeros',
                    bias=True
                ),
                torch.nn.LeakyReLU(0.2, True)
                # torch.nn.SELU(inplace = True)
            )

        def warp(tenInput, tenFlow):
            k = (str(tenFlow.device), str(tenFlow.size()))
            if k not in backwarp_tenGrid:
                tenHorizontal = torch.linspace(-1.0, 1.0, tenFlow.shape[3]).view(1, 1, 1, tenFlow.shape[3]).expand(tenFlow.shape[0], -1, tenFlow.shape[2], -1)
                tenVertical = torch.linspace(-1.0, 1.0, tenFlow.shape[2]).view(1, 1, tenFlow.shape[2], 1).expand(tenFlow.shape[0], -1, -1, tenFlow.shape[3])
                backwarp_tenGrid[k] = torch.cat([ tenHorizontal, tenVertical ], 1).to(device=tenInput.device, dtype=tenInput.dtype)
            tenFlow = torch.cat([ tenFlow[:, 0:1, :, :] / ((tenInput.shape[3] - 1.0) / 2.0), tenFlow[:, 1:2, :, :] / ((tenInput.shape[2] - 1.0) / 2.0) ], 1)

            g = (backwarp_tenGrid[k] + tenFlow).permute(0, 2, 3, 1)
            return torch.nn.functional.grid_sample(input=tenInput, grid=g, mode='bilinear', padding_mode='reflection', align_corners=True)

        class ChannelAttention(Module):
            def __init__(self, in_channels, reduction_ratio=16):
                super(ChannelAttention, self).__init__()
                self.avg_pool = torch.nn.AdaptiveAvgPool2d(1)  # Global average pooling
                self.max_pool = torch.nn.AdaptiveMaxPool2d(1)  # Global max pooling

                # Shared MLP layers
                self.mlp = torch.nn.Sequential(
                    torch.nn.Linear(in_channels, in_channels // reduction_ratio, bias=False),
                    torch.nn.LeakyReLU(0.2, True),
                    torch.nn.Linear(in_channels // reduction_ratio, in_channels, bias=False)
                )
                self.sigmoid = torch.nn.Sigmoid()
                self.beta = torch.nn.Parameter(torch.ones((1, in_channels, 1, 1)), requires_grad=True)
                self.gamma = torch.nn.Parameter(torch.ones((1, in_channels, 1, 1)), requires_grad=True)

            def forward(self, x):
                batch_size, channels, _, _ = x.size()

                # Apply average pooling and reshape
                avg_pool = self.avg_pool(x).view(batch_size, channels)
                # Apply max pooling and reshape
                max_pool = self.max_pool(x).view(batch_size, channels)

                # Forward pass through MLP
                avg_out = self.mlp(avg_pool)
                max_out = self.mlp(max_pool)

                # Combine outputs and apply sigmoid activation
                out = avg_out + max_out
                out = self.sigmoid(out).view(batch_size, channels, 1, 1)

                out = out.expand_as(x)
                out = out * self.beta + self.gamma

                # Scale input feature maps
                return x * out

        class SpatialAttention(Module):
            def __init__(self, kernel_size=7):
                super(SpatialAttention, self).__init__()
                padding = kernel_size // 2  # Ensure same spatial dimensions
                self.conv = torch.nn.Conv2d(2, 1, kernel_size, padding=padding, bias=False)
                self.sigmoid = torch.nn.Sigmoid()

            def forward(self, x):
                # Compute average and max along the channel dimension
                avg_out = torch.mean(x, dim=1, keepdim=True)
                max_out, _ = torch.max(x, dim=1, keepdim=True)

                # Concatenate along channel dimension
                x_cat = torch.cat([avg_out, max_out], dim=1)

                # Apply convolution and sigmoid activation
                out = self.conv(x_cat)
                out = self.sigmoid(out)

                # Scale input feature maps
                return x * out.expand_as(x)

        class CBAM(Module):
            def __init__(self, in_channels, reduction_ratio=16, spatial_kernel_size=7):
                super(CBAM, self).__init__()
                self.channel_attention = ChannelAttention(in_channels, reduction_ratio)
                self.spatial_attention = SpatialAttention(spatial_kernel_size)

            def forward(self, x):
                # Apply channel attention module
                x = self.channel_attention(x)
                # Apply spatial attention module
                # x = self.spatial_attention(x)
                return x

        class Head(Module):
            def __init__(self):
                super(Head, self).__init__()
                self.cnn0 = torch.nn.Conv2d(3, 32, 3, 2, 1)
                self.cnn1 = torch.nn.Conv2d(32, 32, 3, 1, 1)
                self.cnn2 = torch.nn.Conv2d(32, 32, 3, 1, 1)
                self.cnn3 = torch.nn.ConvTranspose2d(32, 8, 4, 2, 1)
                self.relu = torch.nn.LeakyReLU(0.2, True)
                self.encode = torch.nn.Sequential(
                    self.cnn0,
                    self.relu,
                    self.cnn1,
                    self.relu,
                    self.cnn2,
                    self.relu,
                    self.cnn3
                )

            def forward(self, x):
                return self.encode(x)
                '''
                x0 = self.cnn0(x)
                x = self.relu(x0)
                x1 = self.cnn1(x)
                x = self.relu(x1)
                x2 = self.cnn2(x)
                x = self.relu(x2)
                x3 = self.cnn3(x)
                if feat:
                    return [x0, x1, x2, x3]
                return x3
                '''

        class ResConv(Module):
            def __init__(self, c, dilation=1):
                super().__init__()
                self.conv = torch.nn.Conv2d(c, c, 3, 1, dilation, dilation = dilation, groups = 1, padding_mode = 'reflect', bias=True)
                self.beta = torch.nn.Parameter(torch.ones((1, c, 1, 1)), requires_grad=True)        
                self.relu = torch.nn.LeakyReLU(0.2, True) # torch.nn.SELU(inplace = True)

                torch.nn.init.kaiming_normal_(self.conv.weight, mode='fan_in', nonlinearity='relu')
                self.conv.weight.data *= 1e-2
                if self.conv.bias is not None:
                    torch.nn.init.constant_(self.conv.bias, 0)

            def forward(self, x):
                return self.relu(self.conv(x) * self.beta + x)

        class Flownet(Module):
            def __init__(self, in_planes, c=64):
                super().__init__()
                self.conv0 = torch.nn.Sequential(
                    conv(in_planes, c//2, 3, 2, 1),
                    conv(c//2, c, 3, 2, 1),
                    )
                self.conv1 = torch.nn.Sequential(
                    conv(in_planes, c//2, 3, 2, 1),
                    conv(c//2, c, 3, 2, 1),
                    conv(c, c, 3, 2, 1),
                    )

                self.convblock = torch.nn.Sequential(
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                )
                self.convblock_deep = torch.nn.Sequential(
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                    torch.nn.ConvTranspose2d(c, c, 4, 2, 1)
                )

                self.mix = torch.nn.Conv2d(c*2, c*2, kernel_size=1, stride=1, padding=0, bias=True)

                self.attention = CBAM(c*2)
                
                self.convblock_mix = torch.nn.Sequential(
                    ResConv(c*2),
                    ResConv(c*2),
                    ResConv(c*2),
                    ResConv(c*2),
                )
                self.lastconv = torch.nn.Sequential(
                    torch.nn.ConvTranspose2d(c*2, c, 6, 2, 2),
                    torch.nn.Conv2d(c, c, kernel_size=1, stride=1, padding=0, bias=True),
                    torch.nn.ConvTranspose2d(c, c, 4, 2, 1),
                    torch.nn.Conv2d(c, 6, kernel_size=1, stride=1, padding=0, bias=True),
                )

            def forward(self, img0, img1, f0, f1, timestep, mask, flow, scale=1):
                if flow is None:
                    x = torch.cat((img0, img1, f0, f1, timestep), 1)
                    x = torch.nn.functional.interpolate(x, scale_factor= 1. / scale, mode="bilinear", align_corners=False)
                else:
                    warped_img0 = warp(img0, flow[:, :2])
                    warped_img1 = warp(img0, flow[:, :2])
                    warped_f0 = warp(f0, flow[:, :2])
                    warped_f1 = warp(f1, flow[:, 2:4])
                    x = torch.cat((warped_img0, warped_img1, warped_f0, warped_f1, timestep, mask), 1)
                    x = torch.nn.functional.interpolate(x, scale_factor= 1. / scale, mode="bilinear", align_corners=False)
                    flow = torch.nn.functional.interpolate(flow, scale_factor= 1. / scale, mode="bilinear", align_corners=False) * 1. / scale
                    x = torch.cat((x, flow), 1)

                feat = self.conv0(x)
                feat_deep = self.conv1(x)
                feat = self.convblock(feat)
                feat_deep = self.convblock_deep(feat_deep)
                feat = torch.cat((feat_deep, feat), 1)
                feat = self.mix(feat)
                feat = self.attention(feat)
                feat = self.convblock_mix(feat)
                tmp = self.lastconv(feat)
                tmp = torch.nn.functional.interpolate(tmp, scale_factor=scale, mode="bilinear", align_corners=False)
                flow = tmp[:, :4] * scale
                mask = tmp[:, 4:5]
                conf = tmp[:, 5:6]
                return flow, mask, conf

        class FlownetCas(Module):
            def __init__(self):
                super().__init__()
                self.block0 = Flownet(7+16, c=192)
                self.block1 = Flownet(8+4+16, c=128)
                self.block2 = Flownet(8+4+16, c=96)
                self.block3 = Flownet(8+4+16, c=48)
                self.encode = Head()

            def forward(self, img0, img1, timestep=0.5, scale=[8, 4, 2, 1], iterations=1):
                f0 = self.encode(img0)
                f1 = self.encode(img1)

                if not torch.is_tensor(timestep):
                    timestep = (img0[:, :1].clone() * 0 + 1) * timestep

                flow_list = [None] * 4
                mask_list = [None] * 4
                merged = [None] * 4

                scale[0] = 1

                flow, mask, conf = self.block0(img0, img1, f0, f1, timestep, None, None, scale=scale[0])

                flow_list[0] = flow.clone()
                mask_list[0] = torch.sigmoid(mask.clone())
                merged[0] = warp(img0, flow[:, :2]) * mask_list[0] + warp(img1, flow[:, 2:4]) * (1 - mask_list[0])
                
                flow_list[3] = flow_list[0]
                mask_list[3] = mask_list[0]
                merged[3] = merged[0]

                return flow_list, mask_list, merged


                for iteration in range(iterations):
                    flow_d, mask, conf = self.block1(
                        img0, 
                        img1,
                        f0,
                        f1,
                        timestep,
                        mask,
                        flow, 
                        scale=scale[1]
                    )
                    flow = flow + flow_d

                flow_list[1] = flow.clone()
                mask_list[1] = torch.sigmoid(mask.clone())
                merged[1] = warp(img0, flow[:, :2]) * mask_list[1] + warp(img1, flow[:, 2:4]) * (1 - mask_list[1])

                for iteration in range(iterations):
                    flow_d, mask, conf = self.block2(
                        img0, 
                        img1,
                        f0,
                        f1,
                        timestep,
                        mask,
                        flow, 
                        scale=scale[2]
                    )
                    flow = flow + flow_d

                flow_list[2] = flow.clone()
                mask_list[2] = torch.sigmoid(mask.clone())
                merged[2] = warp(img0, flow[:, :2]) * mask_list[2] + warp(img1, flow[:, 2:4]) * (1 - mask_list[2])

                for iteration in range(iterations):
                    flow_d, mask, conf = self.block3(
                        img0, 
                        img1,
                        f0,
                        f1,
                        timestep,
                        mask,
                        flow, 
                        scale=scale[3]
                    )
                    flow = flow + flow_d

                flow_list[3] = flow
                mask_list[3] = torch.sigmoid(mask)
                merged[3] = warp(img0, flow[:, :2]) * mask_list[3] + warp(img1, flow[:, 2:4]) * (1 - mask_list[3])

                return flow_list, mask_list, merged

        self.model = FlownetCas
        self.training_model = FlownetCas

    @staticmethod
    def get_info():
        return Model.info

    @staticmethod
    def get_name():
        return Model.info.get('name')

    @staticmethod
    def input_channels(model_state_dict):
        channels = 3
        try:
            channels = model_state_dict.get('multiresblock1.conv_3x3.conv1.weight').shape[1]
        except Exception as e:
            print (f'Unable to get model dict input channels - setting to 3, {e}')
        return channels

    @staticmethod
    def output_channels(model_state_dict):
        channels = 5
        try:
            channels = model_state_dict.get('conv_final.conv1.weight').shape[0]
        except Exception as e:
            print (f'Unable to get model dict output channels - setting to 3, {e}')
        return channels

    def get_model(self):
        import platform
        if platform.system() == 'Darwin':
            return self.training_model
        return self.model

    def get_training_model(self):
        return self.training_model

    def load_model(self, path, flownet, rank=0):
        import torch
        def convert(param):
            if rank == -1:
                return {
                    k.replace("module.", ""): v
                    for k, v in param.items()
                    if "module." in k
                }
            else:
                return param
        if rank <= 0:
            if torch.cuda.is_available():
                flownet.load_state_dict(convert(torch.load(path)), False)
            else:
                flownet.load_state_dict(convert(torch.load(path, map_location ='cpu')), False)