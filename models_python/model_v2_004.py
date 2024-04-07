class Model:
    def __init__(self, status = dict(), torch = None):
        if torch is None:
            import torch
        Module = torch.nn.Module

        def conv(in_planes, out_planes, kernel_size=3, stride=1, padding=1, dilation=1):
            return torch.nn.Sequential(
                torch.nn.Conv2d(in_planes, out_planes, kernel_size=kernel_size, stride=stride,
                        padding=padding, dilation=dilation, bias=True),
                torch.nn.PReLU(out_planes)
            )

        def deconv(in_planes, out_planes, kernel_size=4, stride=2, padding=1):
            return torch.nn.Sequential(
                torch.nn.ConvTranspose2d(in_channels=in_planes, out_channels=out_planes,
                                        kernel_size=4, stride=2, padding=1, bias=True),
                torch.nn.PReLU(out_planes)
            )

        def warp(tenInput, tenFlow):
            backwarp_tenGrid = {}

            k = (str(tenFlow.device), str(tenFlow.size()))
            if k not in backwarp_tenGrid:
                tenHorizontal = torch.linspace(-1.0, 1.0, tenFlow.shape[3]).view(1, 1, 1, tenFlow.shape[3]).expand(tenFlow.shape[0], -1, tenFlow.shape[2], -1)
                tenVertical = torch.linspace(-1.0, 1.0, tenFlow.shape[2]).view(1, 1, tenFlow.shape[2], 1).expand(tenFlow.shape[0], -1, -1, tenFlow.shape[3])
                backwarp_tenGrid[k] = torch.cat([ tenHorizontal, tenVertical ], 1).to(device=tenInput.device)
                # end

            tenFlow = torch.cat([ tenFlow[:, 0:1, :, :] / ((tenInput.shape[3] - 1.0) / 2.0), tenFlow[:, 1:2, :, :] / ((tenInput.shape[2] - 1.0) / 2.0) ], 1)

            g = (backwarp_tenGrid[k] + tenFlow).permute(0, 2, 3, 1)
            return torch.nn.functional.grid_sample(input=tenInput, grid=g, mode='bilinear', padding_mode='border', align_corners=True)

        class Conv2(Module):
            def __init__(self, in_planes, out_planes, stride=2):
                super().__init__()
                self.conv1 = conv(in_planes, out_planes, 3, stride, 1)
                self.conv2 = conv(out_planes, out_planes, 3, 1, 1)

            def forward(self, x):
                x = self.conv1(x)
                x = self.conv2(x)
                return x

        class ContextNet(Module):
            def __init__(self):
                c = 32
                super().__init__()
                self.conv0 = Conv2(3, c)
                self.conv1 = Conv2(c, c)
                self.conv2 = Conv2(c, 2*c)
                self.conv3 = Conv2(2*c, 4*c)
                self.conv4 = Conv2(4*c, 8*c)

            def forward(self, x, flow):
                x = self.conv0(x)
                x = self.conv1(x)
                flow = F.interpolate(flow, scale_factor=0.5, mode="bilinear", align_corners=False) * 0.5
                f1 = warp(x, flow)
                x = self.conv2(x)
                flow = F.interpolate(flow, scale_factor=0.5, mode="bilinear",
                                    align_corners=False) * 0.5
                f2 = warp(x, flow)
                x = self.conv3(x)
                flow = F.interpolate(flow, scale_factor=0.5, mode="bilinear",
                                    align_corners=False) * 0.5
                f3 = warp(x, flow)
                x = self.conv4(x)
                flow = F.interpolate(flow, scale_factor=0.5, mode="bilinear",
                                    align_corners=False) * 0.5
                f4 = warp(x, flow)
                return [f1, f2, f3, f4]

        class IFBlock(Module):
            def __init__(self, in_planes, scale=1, c=64):
                super(IFBlock, self).__init__()
                self.scale = scale
                self.conv0 = torch.nn.Sequential(
                    conv(in_planes, c, 3, 2, 1),
                    conv(c, 2*c, 3, 2, 1),
                    )
                self.convblock = torch.nn.Sequential(
                    conv(2*c, 2*c),
                    conv(2*c, 2*c),
                    conv(2*c, 2*c),
                    conv(2*c, 2*c),
                    conv(2*c, 2*c),
                    conv(2*c, 2*c),
                )        
                self.conv1 = torch.nn.ConvTranspose2d(2*c, 4, 4, 2, 1)
                            
            def forward(self, x):
                if self.scale != 1:
                    x = torch.nn.functional.interpolate(
                        x, 
                        scale_factor=1. / self.scale,
                        mode="bilinear",
                        align_corners=False
                        )
                x = self.conv0(x)
                x = self.convblock(x)
                x = self.conv1(x)
                flow = x
                if self.scale != 1:
                    flow = torch.nn.functional.interpolate(
                        flow, 
                        scale_factor=self.scale, 
                        mode="bilinear",
                        align_corners=False
                        )
                return flow

        class IFNet(nn.Module):
            def __init__(self):
                super(IFNet, self).__init__()
                self.block0 = IFBlock(6, scale=8, c=192)
                self.block1 = IFBlock(10, scale=4, c=128)
                self.block2 = IFBlock(10, scale=2, c=96)
                self.block3 = IFBlock(10, scale=1, c=48)

            def forward(self, x, UHD=False):
                if UHD:
                    x = torch.nn.functional.interpolate(x, scale_factor=0.5, mode="bilinear", align_corners=False)
                flow0 = self.block0(x)
                F1 = flow0
                F1_large = torch.nn.functional.interpolate(F1, scale_factor=2.0, mode="bilinear", align_corners=False, recompute_scale_factor=False) * 2.0
                warped_img0 = warp(x[:, :3], F1_large[:, :2])
                warped_img1 = warp(x[:, 3:], F1_large[:, 2:4])
                flow1 = self.block1(torch.cat((warped_img0, warped_img1, F1_large), 1))
                F2 = (flow0 + flow1)
                F2_large = torch.nn.functional.interpolate(F2, scale_factor=2.0, mode="bilinear", align_corners=False, recompute_scale_factor=False) * 2.0
                warped_img0 = warp(x[:, :3], F2_large[:, :2])
                warped_img1 = warp(x[:, 3:], F2_large[:, 2:4])
                flow2 = self.block2(torch.cat((warped_img0, warped_img1, F2_large), 1))
                F3 = (flow0 + flow1 + flow2)
                F3_large = torch.nn.functional.interpolate(F3, scale_factor=2.0, mode="bilinear", align_corners=False, recompute_scale_factor=False) * 2.0
                warped_img0 = warp(x[:, :3], F3_large[:, :2])
                warped_img1 = warp(x[:, 3:], F3_large[:, 2:4])
                flow3 = self.block3(torch.cat((warped_img0, warped_img1, F3_large), 1))
                F4 = (flow0 + flow1 + flow2 + flow3)
                return F4, [F1, F2, F3, F4]

        class FusionNet(Module):
            def __init__(self):
                super(FusionNet, self).__init__()
                c = 32
                self.conv0 = Conv2(10, c)
                self.down0 = Conv2(c, 2*c)
                self.down1 = Conv2(4*c, 4*c)
                self.down2 = Conv2(8*c, 8*c)
                self.down3 = Conv2(16*c, 16*c)
                self.up0 = deconv(32*c, 8*c)
                self.up1 = deconv(16*c, 4*c)
                self.up2 = deconv(8*c, 2*c)
                self.up3 = deconv(4*c, c)
                self.conv = torch.nn.ConvTranspose2d(c, 4, 4, 2, 1)

            def forward(self, img0, img1, flow, c0, c1, flow_gt):
                warped_img0 = warp(img0, flow[:, :2])
                warped_img1 = warp(img1, flow[:, 2:4])
                if flow_gt == None:
                    warped_img0_gt, warped_img1_gt = None, None
                else:
                    warped_img0_gt = warp(img0, flow_gt[:, :2])
                    warped_img1_gt = warp(img1, flow_gt[:, 2:4])
                x = self.conv0(torch.cat((warped_img0, warped_img1, flow), 1))
                s0 = self.down0(x)
                s1 = self.down1(torch.cat((s0, c0[0], c1[0]), 1))
                s2 = self.down2(torch.cat((s1, c0[1], c1[1]), 1))
                s3 = self.down3(torch.cat((s2, c0[2], c1[2]), 1))
                x = self.up0(torch.cat((s3, c0[3], c1[3]), 1))
                x = self.up1(torch.cat((x, s2), 1))
                x = self.up2(torch.cat((x, s1), 1))
                x = self.up3(torch.cat((x, s0), 1))
                x = self.conv(x)
                return x, warped_img0, warped_img1, warped_img0_gt, warped_img1_gt
            



        class Model:
            def __init__(self, local_rank=-1):
                self.flownet = IFNet()
                self.contextnet = ContextNet()
                self.fusionnet = FusionNet()
                self.device()
                self.optimG = AdamW(itertools.chain(
                    self.flownet.parameters(),
                    self.contextnet.parameters(),
                    self.fusionnet.parameters()), lr=1e-6, weight_decay=1e-5)
                self.schedulerG = optim.lr_scheduler.CyclicLR(
                    self.optimG, base_lr=1e-6, max_lr=1e-3, step_size_up=8000, cycle_momentum=False)
                self.epe = EPE()
                self.ter = Ternary()
                self.sobel = SOBEL()
                if local_rank != -1:
                    self.flownet = DDP(self.flownet, device_ids=[
                                    local_rank], output_device=local_rank)
                    self.contextnet = DDP(self.contextnet, device_ids=[
                                        local_rank], output_device=local_rank)
                    self.fusionnet = DDP(self.fusionnet, device_ids=[
                                        local_rank], output_device=local_rank)

            def train(self):
                self.flownet.train()
                self.contextnet.train()
                self.fusionnet.train()

            def eval(self):
                self.flownet.eval()
                self.contextnet.eval()
                self.fusionnet.eval()

            def device(self):
                self.flownet.to(device)
                self.contextnet.to(device)
                self.fusionnet.to(device)

            def load_model(self, path, rank):
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
                    self.flownet.load_state_dict(
                        convert(torch.load('{}/flownet.pkl'.format(path), map_location=device)))
                    self.contextnet.load_state_dict(
                        convert(torch.load('{}/contextnet.pkl'.format(path), map_location=device)))
                    self.fusionnet.load_state_dict(
                        convert(torch.load('{}/unet.pkl'.format(path), map_location=device)))

            def save_model(self, path, rank):
                if rank == 0:
                    torch.save(self.flownet.state_dict(), '{}/flownet.pkl'.format(path))
                    torch.save(self.contextnet.state_dict(), '{}/contextnet.pkl'.format(path))
                    torch.save(self.fusionnet.state_dict(), '{}/unet.pkl'.format(path))

            def predict(self, imgs, flow, training=True, flow_gt=None, UHD=False):
                img0 = imgs[:, :3]
                img1 = imgs[:, 3:]
                if UHD:
                    flow = F.interpolate(flow, scale_factor=2.0, mode="bilinear", align_corners=False) * 2.0
                c0 = self.contextnet(img0, flow[:, :2])
                c1 = self.contextnet(img1, flow[:, 2:4])
                flow = F.interpolate(flow, scale_factor=2.0, mode="bilinear",
                                    align_corners=False) * 2.0
                refine_output, warped_img0, warped_img1, warped_img0_gt, warped_img1_gt = self.fusionnet(
                    img0, img1, flow, c0, c1, flow_gt)
                res = torch.sigmoid(refine_output[:, :3]) * 2 - 1
                mask = torch.sigmoid(refine_output[:, 3:4])
                merged_img = warped_img0 * mask + warped_img1 * (1 - mask)
                pred = merged_img + res
                # pred = torch.clamp(pred, 0, 1)
                if training:
                    return pred, mask, merged_img, warped_img0, warped_img1, warped_img0_gt, warped_img1_gt
                else:
                    return pred

            def inference(self, img0, img1, UHD=False):
                imgs = torch.cat((img0, img1), 1)
                flow, _ = self.flownet(imgs, UHD)
                return self.predict(imgs, flow, training=False, UHD=UHD)

            def update(self, imgs, gt, learning_rate=0, mul=1, training=True, flow_gt=None):
                for param_group in self.optimG.param_groups:
                    param_group['lr'] = learning_rate
                if training:
                    self.train()
                else:
                    self.eval()
                flow, flow_list = self.flownet(imgs)
                pred, mask, merged_img, warped_img0, warped_img1, warped_img0_gt, warped_img1_gt = self.predict(
                    imgs, flow, flow_gt=flow_gt)
                loss_ter = self.ter(pred, gt).mean()
                if training:
                    with torch.no_grad():
                        loss_flow = torch.abs(warped_img0_gt - gt).mean()
                        loss_mask = torch.abs(
                            merged_img - gt).sum(1, True).float().detach()
                        loss_mask = F.interpolate(loss_mask, scale_factor=0.5, mode="bilinear",
                                                align_corners=False).detach()
                        flow_gt = (F.interpolate(flow_gt, scale_factor=0.5, mode="bilinear",
                                                align_corners=False) * 0.5).detach()
                    loss_cons = 0
                    for i in range(4):
                        loss_cons += self.epe(flow_list[i][:, :2], flow_gt[:, :2], 1)
                        loss_cons += self.epe(flow_list[i][:, 2:4], flow_gt[:, 2:4], 1)
                    loss_cons = loss_cons.mean() * 0.01
                else:
                    loss_cons = torch.tensor([0])
                    loss_flow = torch.abs(warped_img0 - gt).mean()
                    loss_mask = 1
                loss_l1 = (((pred - gt) ** 2 + 1e-6) ** 0.5).mean()
                if training:
                    self.optimG.zero_grad()
                    loss_G = loss_l1 + loss_cons + loss_ter
                    loss_G.backward()
                    self.optimG.step()
                return pred, merged_img, flow, loss_l1, loss_flow, loss_cons, loss_ter, loss_mask


    @staticmethod
    def get_name():
        return 'model_v2_004'

    @staticmethod
    def get_file_name():
        import os
        return os.path.basename(__file__)

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
