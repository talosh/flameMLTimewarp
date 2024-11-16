# Orig v001 changed to v002 main flow and signatures
# Back from SiLU to LeakyReLU to test data flow
# Warps moved to flownet forward
# Different Tail from flownet 2lh (ConvTr 6x6, conv 1x1, ConvTr 4x4, conv 1x1)

class Model:

    info = {
        'name': 'Flownet4_v001d',
        'file': 'flownet4_v001d.py',
        'ratio_support': True
    }

    def __init__(self, status = dict(), torch = None):
        if torch is None:
            import torch
        Module = torch.nn.Module
        backwarp_tenGrid = {}
        backwarp_tenGrid_norm = {}

        def conv(in_planes, out_planes, kernel_size=3, stride=1, padding=1, dilation=1):
            return torch.nn.Sequential(
                torch.nn.Conv2d(
                    in_planes, 
                    out_planes, 
                    kernel_size=kernel_size, 
                    stride=stride,
                    padding=padding, 
                    dilation=dilation,
                    padding_mode = 'zeros',
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
            # tenFlow = torch.cat([ tenFlow[:, 0:1, :, :] / ((tenInput.shape[3] - 1.0) / 2.0), tenFlow[:, 1:2, :, :] / ((tenInput.shape[2] - 1.0) / 2.0) ], 1)
            g = (backwarp_tenGrid[k] + tenFlow).permute(0, 2, 3, 1)
            return tenInput # torch.nn.functional.grid_sample(input=tenInput, grid=g, mode='bilinear', padding_mode='border', align_corners=True)

        class Head(Module):
            def __init__(self):
                super(Head, self).__init__()
                self.cnn0 = torch.nn.Conv2d(3, 32, 3, 2, 1)
                self.cnn1 = torch.nn.Conv2d(32, 32, 3, 1, 1)
                self.cnn2 = torch.nn.Conv2d(32, 32, 3, 1, 1)
                self.cnn3 = torch.nn.ConvTranspose2d(32, 8, 4, 2, 1)
                self.relu = torch.nn.LeakyReLU(0.2, True)

            def forward(self, x, feat=False):
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

        class ResConv(Module):
            def __init__(self, c, dilation=1):
                super().__init__()
                self.conv = torch.nn.Conv2d(c, c, 3, 1, dilation, dilation = dilation, groups = 1, padding_mode = 'zeros', bias=True)
                self.beta = torch.nn.Parameter(torch.ones((1, c, 1, 1)), requires_grad=True)        
                self.relu = torch.nn.LeakyReLU(0.2, True) # torch.nn.SELU(inplace = True)
            def forward(self, x):
                return self.relu(self.conv(x) * self.beta + x)

        class Flownet(Module):
            def __init__(self, in_planes, c=64):
                super().__init__()
                self.conv0 = conv(in_planes - 1, c//2, 3, 2, 1)
                self.conv1 = conv(c//2 + 3, c, 3, 2, 1)
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
                self.lastconv = torch.nn.Sequential(
                    torch.nn.ConvTranspose2d(c, 4*6, 4, 2, 1),
                    torch.nn.PixelShuffle(2)
                )
                self.maxdepth = 4

            def forward(self, img0, img1, f0, f1, timestep, mask, flow, scale=1):
                n, c, h, w = img0.shape
                sh, sw = round(h * (1 / scale)), round(w * (1 / scale))
                
                if flow is None:
                    x = torch.cat((img0, img1, f0, f1), 1)
                    x = torch.nn.functional.interpolate(x, scale_factor= 1. / scale, mode="bilinear", align_corners=False)
                else:
                    flow[:, 0:1, :, :] = flow[:, 0:1, :, :] / ((flow.shape[3] - 1.0) / 2.0)
                    flow[:, 1:2, :, :] = flow[:, 1:2, :, :] / ((flow.shape[2] - 1.0) / 2.0)
                    flow[:, 2:3, :, :] = flow[:, 2:3, :, :] / ((flow.shape[3] - 1.0) / 2.0)
                    flow[:, 3:4, :, :] = flow[:, 3:4, :, :] / ((flow.shape[2] - 1.0) / 2.0)

                    warped_img0 = warp(img0, flow[:, :2])
                    warped_img1 = warp(img1, flow[:, 2:4])
                    warped_f0 = warp(f0, flow[:, :2])
                    warped_f1 = warp(f1, flow[:, 2:4])
                    x = torch.cat((warped_img0, warped_img1, warped_f0, warped_f1, mask), 1)
                    x = torch.nn.functional.interpolate(x, scale_factor= 1. / scale, mode="bilinear", align_corners=False)
                    flow = torch.nn.functional.interpolate(flow, scale_factor= 1. / scale, mode="bilinear", align_corners=False) # * 1. / scale
                    x = torch.cat((x, flow), 1)

                ph = self.maxdepth - (sh % self.maxdepth)
                pw = self.maxdepth - (sw % self.maxdepth)
                padding = (0, pw, 0, ph)
                x = torch.nn.functional.pad(x, padding, mode='constant')

                n, _, xh, xw = x.shape
                tenHorizontal = torch.linspace(-1.0, 1.0, xw//2).view(1, 1, 1, xw//2).expand(n, -1, xh//2, -1)
                tenVertical = torch.linspace(-1.0, 1.0, xh//2).view(1, 1, xh//2, 1).expand(n, -1, -1, xw//2)
                tenGrid = torch.cat([ 
                    tenHorizontal,
                    tenVertical
                    ], 1).to(device=img0.device, dtype=img0.dtype)
                timestep = (tenGrid[:, :1].clone() * 0 + 1) * timestep
                y = torch.cat((timestep, tenGrid), 1)

                # y = torch.zeros(n, 3, xh//2, xw//2).to(device=x.device, dtype=x.dtype)

                feat = self.conv0(x)
                feat = torch.cat((feat, y), 1)
                feat = self.conv1(feat)
                feat = self.convblock(feat)
                tmp = self.lastconv(feat)
                tmp = torch.nn.functional.interpolate(tmp[:, :, :sh, :sw], size=(h, w), mode="bilinear", align_corners=False)
                flow = tmp[:, :4] # * scale
                mask = tmp[:, 4:5]
                conf = tmp[:, 5:6]

                flow[:, 0:1, :, :] = flow[:, 0:1, :, :] * ((flow.shape[3] - 1.0) / 2.0)
                flow[:, 1:2, :, :] = flow[:, 1:2, :, :] * ((flow.shape[2] - 1.0) / 2.0)
                flow[:, 2:3, :, :] = flow[:, 2:3, :, :] * ((flow.shape[3] - 1.0) / 2.0)
                flow[:, 3:4, :, :] = flow[:, 3:4, :, :] * ((flow.shape[2] - 1.0) / 2.0)

                return flow, mask, conf

        class FlownetCas(Module):
            def __init__(self):
                super().__init__()
                self.block0 = Flownet(7+16, c=192)
                self.block1 = Flownet(8+4+16, c=128)
                self.block2 = Flownet(8+4+16, c=96)
                self.block3 = Flownet(8+4+16, c=64)
                self.encode = Head()

            def forward(self, img0, img1, timestep=0.5, scale=[16, 8, 4, 1], iterations=1):
                img0 = img0
                img1 = img1
                f0 = self.encode(img0)
                f1 = self.encode(img1)

                flow_list = [None] * 4
                mask_list = [None] * 4
                conf_list = [None] * 4
                merged = [None] * 4

                flow, mask, conf = self.block0(img0, img1, f0, f1, timestep, None, None, scale=scale[0])

                '''
                flow_list[0] = flow.clone()
                conf_list[0] = torch.sigmoid(conf.clone())
                mask_list[0] = torch.sigmoid(mask.clone())
                merged[0] = warp(img0, flow[:, :2]) * mask_list[0] + warp(img1, flow[:, 2:4]) * (1 - mask_list[0])
                '''

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

                '''
                flow_list[1] = flow.clone()
                conf_list[1] = torch.sigmoid(conf.clone())
                mask_list[1] = torch.sigmoid(mask.clone())
                merged[1] = warp(img0, flow[:, :2]) * mask_list[1] + warp(img1, flow[:, 2:4]) * (1 - mask_list[1])
                '''

                for iteration in range(iterations):
                    flow_d, mask_d, conf_d = self.block2(
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
                    mask = mask + mask_d
                    conf = conf + conf_d

                '''
                flow_list[2] = flow.clone()
                conf_list[2] = torch.sigmoid(conf.clone())
                mask_list[2] = torch.sigmoid(mask.clone())
                merged[2] = warp(img0, flow[:, :2]) * mask_list[2] + warp(img1, flow[:, 2:4]) * (1 - mask_list[2])
                '''

                for iteration in range(iterations):
                    flow_d, mask_d, conf_d = self.block3(
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
                    mask = mask + mask_d
                    conf = conf + conf_d

                # fs2 = ((flow.shape[2] - 1.0) / 2.0)
                # fs3 = ((flow.shape[3] - 1.0) / 2.0)
                # flow[:, 0:1, :, :] = flow[:, 0:1, :, :] * fs3
                # flow[:, 1:2, :, :] = flow[:, 1:2, :, :] * fs2

                '''
                flow_list[3] = flow # .detach().clone() # torch.tanh(flow.detach().clone())
                flow_list[3][:, 0:1, :, :] = flow[:, 0:1, :, :] * ((flow.shape[3] - 1.0) / 2.0)
                flow_list[3][:, 1:2, :, :] = flow[:, 1:2, :, :] * ((flow.shape[2] - 1.0) / 2.0)
                flow_list[3][:, 2:3, :, :] = flow[:, 2:3, :, :] * ((flow.shape[3] - 1.0) / 2.0)
                flow_list[3][:, 3:4, :, :] = flow[:, 3:4, :, :] * ((flow.shape[2] - 1.0) / 2.0)
                mask_list[3] = torch.sigmoid(mask) # (torch.tanh(mask) + 1) / 2.0
                conf_list[3] = torch.sigmoid(conf) # (torch.tanh(conf) + 1) / 2.0
                merged[3] = warp(img0, flow_list[3][:, :2]) * mask_list[3] + warp(img1, flow_list[3][:, 2:4]) * (1 - mask_list[3])
                '''

                flow_list[3] = flow
                conf_list[3] = torch.sigmoid(conf)
                mask_list[3] = torch.sigmoid(mask)
                merged[3] = warp(img0, flow[:, :2]) * mask_list[3] + warp(img1, flow[:, 2:4]) * (1 - mask_list[3])

                return flow_list, mask_list, conf_list, merged

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