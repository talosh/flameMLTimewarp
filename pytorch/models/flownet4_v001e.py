# Orig v001 changed to v002 main flow and signatures
# Back from SiLU to LeakyReLU to test data flow
# Warps moved to flownet forward
# Different Tail from flownet 2lh (ConvTr 6x6, conv 1x1, ConvTr 4x4, conv 1x1)

class Model:

    info = {
        'name': 'Flownet4_v001e',
        'file': 'flownet4_v001e.py',
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
            tenFlow = torch.cat([ tenFlow[:, 0:1, :, :] / ((tenInput.shape[3] - 1.0) / 2.0), tenFlow[:, 1:2, :, :] / ((tenInput.shape[2] - 1.0) / 2.0) ], 1)

            g = (backwarp_tenGrid[k] + tenFlow).permute(0, 2, 3, 1)
            return torch.nn.functional.grid_sample(input=tenInput, grid=g, mode='bilinear', padding_mode='border', align_corners=True)

        def hpass(img):  
            def gauss_kernel(size=5, channels=3):
                kernel = torch.tensor([[1., 4., 6., 4., 1],
                                    [4., 16., 24., 16., 4.],
                                    [6., 24., 36., 24., 6.],
                                    [4., 16., 24., 16., 4.],
                                    [1., 4., 6., 4., 1.]])
                kernel /= 256.
                kernel = kernel.repeat(channels, 1, 1, 1)
                return kernel
            
            def conv_gauss(img, kernel):
                img = torch.nn.functional.pad(img, (2, 2, 2, 2), mode='reflect')
                out = torch.nn.functional.conv2d(img, kernel, groups=img.shape[1])
                return out

            def normalize(tensor, min_val, max_val):
                return (tensor - min_val) / (max_val - min_val)

            gkernel = gauss_kernel()
            gkernel = gkernel.to(device=img.device, dtype=img.dtype)
            hp = img - conv_gauss(img, gkernel) + 0.5
            hp = torch.clamp(hp, 0.49, 0.51)
            hp = normalize(hp, hp.min(), hp.max())
            hp = torch.max(hp, dim=1, keepdim=True).values
            return hp

        def blur(img):  
            def gauss_kernel(size=5, channels=3):
                kernel = torch.tensor([[1., 4., 6., 4., 1],
                                    [4., 16., 24., 16., 4.],
                                    [6., 24., 36., 24., 6.],
                                    [4., 16., 24., 16., 4.],
                                    [1., 4., 6., 4., 1.]])
                kernel /= 256.
                kernel = kernel.repeat(channels, 1, 1, 1)
                return kernel
            
            def conv_gauss(img, kernel):
                img = torch.nn.functional.pad(img, (2, 2, 2, 2), mode='reflect')
                out = torch.nn.functional.conv2d(img, kernel, groups=img.shape[1])
                return out

            gkernel = gauss_kernel()
            gkernel = gkernel.to(device=img.device, dtype=img.dtype)
            return conv_gauss(img, gkernel)

        def centered_highpass_filter(rgb_image, gamma=1.8):
            padding = 32

            rgb_image = torch.nn.functional.pad(rgb_image, (padding, padding, padding, padding), mode='reflect')
            n, c, h, w = rgb_image.shape

            # Step 1: Apply Fourier Transform along spatial dimensions
            freq_image = torch.fft.fft2(rgb_image, dim=(-2, -1))
            freq_image = torch.fft.fftshift(freq_image, dim=(-2, -1))  # Shift the zero-frequency component to the center

            # Step 2: Calculate the distance of each frequency component from the center
            center_x, center_y = h // 2, w // 2
            x = torch.arange(h).view(-1, 1).repeat(1, w)
            y = torch.arange(w).repeat(h, 1)
            distance_from_center = ((x - center_x) ** 2 + (y - center_y) ** 2).sqrt()
            
            # Normalize distance to the range [0, 1]
            max_distance = distance_from_center.max()
            distance_weight = distance_from_center / max_distance  # Now scaled from 0 (low freq) to 1 (high freq)
            distance_weight = distance_weight.to(freq_image.device)  # Ensure the weight is on the same device as the image
            distance_weight = distance_weight ** (1 / gamma)
            
            k = 11  # Controls the steepness of the curve
            x0 = 0.5  # Midpoint where the function crosses 0.5

            # Compute the S-like function using a sigmoid
            distance_weight = 1 / (1 + torch.exp(-k * (distance_weight - x0)))
            # Step 3: Apply the distance weight to both real and imaginary parts of the frequency components
            freq_image_scaled = freq_image * distance_weight.unsqueeze(0).unsqueeze(1)

            # Step 4: Inverse Fourier Transform to return to spatial domain
            freq_image_scaled = torch.fft.ifftshift(freq_image_scaled, dim=(-2, -1))
            scaled_image = torch.fft.ifft2(freq_image_scaled, dim=(-2, -1)).real  # Take the real part only
            scaled_image = torch.max(scaled_image, dim=1, keepdim=True).values
            # scaled_image = scaled_image ** (1 / 1.8)

            return scaled_image[:, :, padding:-padding, padding:-padding]

        class Head(Module):
            def __init__(self):
                super(Head, self).__init__()
                self.cnn0 = torch.nn.Conv2d(3+1+3, 36, 3, 2, 1)
                self.cnn1 = torch.nn.Conv2d(36, 36, 3, 1, 1)
                self.cnn2 = torch.nn.Conv2d(36, 36, 3, 1, 1)
                self.cnn3 = torch.nn.ConvTranspose2d(36, 9, 4, 2, 1)
                self.relu = torch.nn.Mish(True)

            def forward(self, x):
                hp = centered_highpass_filter(x.float())
                hp = hp.to(dtype = x.dtype)
                blurred = blur(x)
                x = torch.cat((x, hp, blurred), 1)
                x = self.cnn0(x)
                x = self.relu(x)
                x = self.cnn1(x)
                x = self.relu(x)
                x = self.cnn2(x)
                x = self.relu(x)
                x = self.cnn3(x)
                return x

        class ResConv(Module):
            def __init__(self, c, dilation=1):
                super().__init__()
                self.conv = torch.nn.Conv2d(c, c, 3, 1, dilation, dilation = dilation, groups = 1, padding_mode = 'zeros', bias=True)
                self.beta = torch.nn.Parameter(torch.ones((1, c, 1, 1)), requires_grad=True)        
                self.relu = torch.nn.LeakyReLU(0.2, True) # torch.nn.SELU(inplace = True)
            def forward(self, x):
                return self.relu(self.conv(x) * self.beta + x)

        class ResConvMix(Module):
            def __init__(self, c, cd):
                super().__init__()
                self.conv = torch.nn.ConvTranspose2d(cd, c, 4, 2, 1)
                self.beta = torch.nn.Parameter(torch.ones((1, c, 1, 1)), requires_grad=True)
                self.relu = torch.nn.LeakyReLU(0.2, True)

            def forward(self, x, x_deep):
                return self.relu(self.conv(x_deep) * self.beta + x)

        class ResConvRevMix(Module):
            def __init__(self, c, cd):
                super().__init__()
                self.conv = torch.nn.Conv2d(c, cd, 3, 2, 1, padding_mode = 'zeros', bias=True)
                self.beta = torch.nn.Parameter(torch.ones((1, cd, 1, 1)), requires_grad=True)
                self.relu = torch.nn.LeakyReLU(0.2, True)

            def forward(self, x, x_deep):
                return self.relu(self.conv(x) * self.beta + x_deep)

        class Flownet(Module):
            def __init__(self, in_planes, c=64):
                super().__init__()
                self.conv0 = torch.nn.Sequential(
                    conv(in_planes, c//2, 5, 2, 2),
                    conv(c//2, c, 3, 2, 1),
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
                self.lastconv = torch.nn.Sequential(
                    torch.nn.Upsample(scale_factor=2, mode='bilinear'),
                    conv(c, c//2, 3, 1, 1),
                    torch.nn.Upsample(scale_factor=2, mode='bilinear'),
                    torch.nn.Conv2d(c//2, 6, kernel_size=3, stride=1, padding=1, bias=True)
                )
                self.maxdepth = 4

            def forward(self, img0, img1, f0, f1, timestep, mask, flow, scale=1):
                n, c, h, w = img0.shape
                sh, sw = round(h * (1 / scale)), round(w * (1 / scale))

                timestep = (img0[:, :1].clone() * 0 + 1) * timestep
                
                if flow is None:
                    x = torch.cat((img0, img1, f0, f1, timestep), 1)
                    x = torch.nn.functional.interpolate(x, size=(sh, sw), mode="bilinear", align_corners=False)
                else:
                    warped_img0 = warp(img0, flow[:, :2])
                    warped_img1 = warp(img1, flow[:, 2:4])
                    warped_f0 = warp(f0, flow[:, :2])
                    warped_f1 = warp(f1, flow[:, 2:4])
                    x = torch.cat((warped_img0, warped_img1, warped_f0, warped_f1, timestep, mask), 1)
                    x = torch.nn.functional.interpolate(x, size=(sh, sw), mode="bilinear", align_corners=False)
                    flow = torch.nn.functional.interpolate(flow, size=(sh, sw), mode="bilinear", align_corners=False) * 1. / scale
                    x = torch.cat((x, flow), 1)

                ph = self.maxdepth - (sh % self.maxdepth)
                pw = self.maxdepth - (sw % self.maxdepth)
                padding = (0, pw, 0, ph)
                x = torch.nn.functional.pad(x, padding, mode='constant')

                feat = self.conv0(x)
                feat = self.convblock(feat)
                tmp = self.lastconv(feat)
                tmp = torch.nn.functional.interpolate(tmp[:, :, :sh, :sw], size=(h, w), mode="bilinear", align_corners=False)
                flow = tmp[:, :4] * scale
                mask = tmp[:, 4:5]
                conf = tmp[:, 5:6]
                return flow, mask, conf

        class FlownetLT(Module):
            def __init__(self, in_planes, c=64):
                super().__init__()
                self.conv0 = torch.nn.Sequential(
                    conv(in_planes, c, 3, 2, 1),
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
                self.lastconv = torch.nn.Sequential(
                    torch.nn.Upsample(scale_factor=2, mode='bilinear'),
                    conv(c, c, 3, 1, 1),
                    torch.nn.Upsample(scale_factor=2, mode='bilinear'),
                    torch.nn.Conv2d(c, 6, kernel_size=3, stride=1, padding=1, bias=True)
                )
                self.maxdepth = 4

            def forward(self, img0, img1, f0, f1, timestep, mask, flow, scale=1):
                n, c, h, w = img0.shape
                sh, sw = round(h * (1 / scale)), round(w * (1 / scale))

                timestep = (img0[:, :1].clone() * 0 + 1) * timestep
                
                warped_img0 = warp(img0, flow[:, :2])
                warped_img1 = warp(img1, flow[:, 2:4])
                x = torch.cat((warped_img0, warped_img1, timestep, mask), 1)
                x = torch.nn.functional.interpolate(x, size=(sh, sw), mode="bilinear", align_corners=False)
                flow = torch.nn.functional.interpolate(flow, size=(sh, sw), mode="bilinear", align_corners=False) * 1. / scale
                x = torch.cat((x, flow), 1)

                ph = self.maxdepth - (sh % self.maxdepth)
                pw = self.maxdepth - (sw % self.maxdepth)
                padding = (0, pw, 0, ph)
                x = torch.nn.functional.pad(x, padding, mode='constant')

                feat = self.conv0(x)
                feat = self.convblock(feat)
                tmp = self.lastconv(feat)
                tmp = torch.nn.functional.interpolate(tmp[:, :, :sh, :sw], size=(h, w), mode="bilinear", align_corners=False)
                flow = tmp[:, :4] * scale
                mask = tmp[:, 4:5]
                conf = tmp[:, 5:6]
                return flow, mask, conf

        class FlownetDeepSingleHead(Module):
            def __init__(self, in_planes, c=64):
                super().__init__()
                cd = int(1.618 * c)
                self.conv0 = conv(in_planes, c, 7, 2, 3)
                self.conv1 = conv(c, c, 3, 2, 1)
                self.conv2 = conv(c, cd, 3, 2, 1)
                self.convblock_shallow = torch.nn.Sequential(
                    ResConv(c),
                    ResConv(c),
                )
                self.convblock1 = torch.nn.Sequential(
                    ResConv(c),
                    ResConv(c),
                )
                self.convblock2 = torch.nn.Sequential(
                    ResConv(c),
                    ResConv(c),
                )
                self.convblock3 = torch.nn.Sequential(
                    ResConv(c),
                    ResConv(c),
                )
                self.convblock4 = torch.nn.Sequential(
                    ResConv(c),
                    ResConv(c),
                )
                self.convblock_fw = torch.nn.Sequential(
                    ResConv(c),
                )
                self.convblock_bw = torch.nn.Sequential(
                    ResConv(c),
                )
                self.convblock_mask = torch.nn.Sequential(
                    ResConv(c),
                    ResConv(c),
                    ResConv(c),
                )
                self.convblock_deep1 = torch.nn.Sequential(
                    ResConv(cd),
                    ResConv(cd),
                    ResConv(cd),
                    ResConv(cd),
                )
                self.convblock_deep2 = torch.nn.Sequential(
                    ResConv(cd),
                    ResConv(cd),
                    ResConv(cd),
                )
                self.convblock_deep3 = torch.nn.Sequential(
                    ResConv(cd),
                    ResConv(cd),
                )
                self.convblock_deep4 = torch.nn.Sequential(
                    ResConv(cd),
                    ResConv(cd),
                )
                self.mix1 = ResConvMix(c, cd)
                self.mix2 = ResConvMix(c, cd)
                self.mix3 = ResConvMix(c, cd)
                self.mix4 = ResConvMix(c, cd)
                self.revmix1 = ResConvRevMix(c, cd)
                self.revmix2 = ResConvRevMix(c, cd)
                self.lastconv_mask = torch.nn.Sequential(
                    torch.nn.ConvTranspose2d(c, c, 6, 2, 2),
                    torch.nn.Conv2d(c, c, kernel_size=1, stride=1, padding=0, bias=True),
                    torch.nn.ConvTranspose2d(c, c, 4, 2, 1),
                    torch.nn.Conv2d(c, 2, kernel_size=1, stride=1, padding=0, bias=True),
                )
                self.lastconv_fw = torch.nn.Sequential(
                    torch.nn.ConvTranspose2d(c, c, 6, 2, 2),
                    torch.nn.Conv2d(c, c, kernel_size=1, stride=1, padding=0, bias=True),
                    torch.nn.ConvTranspose2d(c, c, 4, 2, 1),
                    torch.nn.Conv2d(c, 2, kernel_size=1, stride=1, padding=0, bias=True),
                )
                self.lastconv_bw = torch.nn.Sequential(
                    torch.nn.ConvTranspose2d(c, c, 6, 2, 2),
                    torch.nn.Conv2d(c, c, kernel_size=1, stride=1, padding=0, bias=True),
                    torch.nn.ConvTranspose2d(c, c, 4, 2, 1),
                    torch.nn.Conv2d(c, 2, kernel_size=1, stride=1, padding=0, bias=True),
                )
                self.maxdepth = 8

            def forward(self, img0, img1, f0, f1, timestep, mask, flow, conf, scale=1):
                n, c, h, w = img0.shape
                sh, sw = round(h * (1 / scale)), round(w * (1 / scale))

                if flow is None:
                    x = torch.cat((img0, img1, f0, f1), 1)
                    x = torch.nn.functional.interpolate(x, size=(sh, sw), mode="bicubic", align_corners=False)
                else:
                    warped_img0 = warp(img0, flow[:, :2])
                    warped_img1 = warp(img1, flow[:, 2:4])
                    warped_f0 = warp(f0, flow[:, :2])
                    warped_f1 = warp(f1, flow[:, 2:4])
                    x = torch.cat((warped_img0, warped_img1, warped_f0, warped_f1, mask, conf), 1)
                    x = torch.nn.functional.interpolate(x, size=(sh, sw), mode="bicubic", align_corners=False)
                    flow = torch.nn.functional.interpolate(flow, size=(sh, sw), mode="bilinear", align_corners=False) * 1. / scale
                    x = torch.cat((x, flow), 1)

                tenHorizontal = torch.linspace(-1.0, 1.0, sw).view(1, 1, 1, sw).expand(n, -1, sh, -1)
                tenVertical = torch.linspace(-1.0, 1.0, sh).view(1, 1, sh, 1).expand(n, -1, -1, sw)
                tenGrid = torch.cat((
                    tenHorizontal * ((sw - 1.0) / 2.0), 
                    tenVertical * ((sh - 1.0) / 2.0)
                    ), 1).to(device=img0.device, dtype=img0.dtype)
                timestep = (tenGrid[:, :1].clone() * 0 + 1) * timestep
                x = torch.cat((x, timestep, tenGrid), 1)

                ph = self.maxdepth - (sh % self.maxdepth)
                pw = self.maxdepth - (sw % self.maxdepth)
                padding = (0, pw, 0, ph)
                x = torch.nn.functional.pad(x, padding)

                # noise = torch.rand_like(feat[:, :2, :, :]) * 2 - 1
                feat = self.conv0(x)
                feat = self.convblock_shallow(feat)
                feat = self.conv1(feat)

                feat_deep = self.conv2(feat)
                feat_deep = self.convblock_deep1(feat_deep)
                feat = self.mix1(feat, feat_deep)

                feat_deep = self.convblock_deep2(feat_deep)
                feat = self.convblock1(feat)

                tmp = self.revmix1(feat, feat_deep)
                feat = self.mix2(feat, feat_deep)

                feat_deep = self.convblock_deep3(tmp)
                feat = self.convblock2(feat)

                tmp = self.revmix2(feat, feat_deep)
                feat = self.mix3(feat, feat_deep)

                feat_deep = self.convblock_deep4(tmp)
                feat = self.convblock3(feat)
                feat = self.mix4(feat, feat_deep)

                feat = self.convblock4(feat)

                feat_mask = self.convblock_mask(feat)
                tmp_mask = self.lastconv_mask(feat_mask)

                feat_fw = self.convblock_fw(feat)
                feat_fw = self.lastconv_fw(feat_fw)

                feat_bw = self.convblock_bw(feat)
                feat_bw = self.lastconv_bw(feat_bw)

                flow = torch.cat((feat_fw, feat_bw), 1)

                tmp_mask = torch.nn.functional.interpolate(tmp_mask[:, :, :sh, :sw], size=(h, w), mode="bicubic", align_corners=False)
                flow = torch.nn.functional.interpolate(flow[:, :, :sh, :sw], size=(h, w), mode="bilinear", align_corners=False)

                flow = flow * scale
                mask = tmp_mask[:, 0:1]
                conf = tmp_mask[:, 1:2]

                return flow, mask, conf

        class FlownetCas(Module):
            def __init__(self):
                super().__init__()
                self.block0 = FlownetDeepSingleHead(6+18+1+2, c=192) # images + feat + timestep + lineargrid
                self.block0ref = FlownetDeepSingleHead(6+18+1+1+1+4+2, c=192) # images + feat + timestep + mask + conf + flow + lineargrid
                self.block1 = Flownet(8+4+16, c=144)
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

                flow_init, mask_init, conf_init = self.block0(img0, img1, f0, f1, timestep, None, None, None, scale=scale[0])

                flow, mask, conf = self.block0ref(
                    img0, 
                    img1,
                    f0,
                    f1,
                    timestep,
                    mask_init,
                    flow_init,
                    conf_init,
                    scale=scale[0]
                )

                flow_list[0] = flow.clone()
                conf_list[0] = torch.sigmoid(conf.clone())
                mask_list[0] = torch.sigmoid(mask.clone())
                merged[0] = warp(img0, flow[:, :2]) * mask_list[0] + warp(img1, flow[:, 2:4]) * (1 - mask_list[0])

                flow_d, mask_d, conf_d = self.block1(
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
                mask = mask + mask_d
                conf = conf + conf_d

                flow_list[1] = flow.clone()
                conf_list[1] = torch.sigmoid(conf.clone())
                mask_list[1] = torch.sigmoid(mask.clone())
                merged[1] = warp(img0, flow[:, :2]) * mask_list[1] + warp(img1, flow[:, 2:4]) * (1 - mask_list[1])

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

                flow_list[2] = flow.clone()
                conf_list[2] = torch.sigmoid(conf.clone())
                mask_list[2] = torch.sigmoid(mask.clone())
                merged[2] = warp(img0, flow[:, :2]) * mask_list[2] + warp(img1, flow[:, 2:4]) * (1 - mask_list[2])

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