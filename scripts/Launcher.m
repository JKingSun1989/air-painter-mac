#import <Cocoa/Cocoa.h>
#import <AVFoundation/AVFoundation.h>

@interface PainterDelegate : NSObject <NSApplicationDelegate>
@property(nonatomic, strong) NSTask *task;
@end

@implementation PainterDelegate
- (void)fail:(NSString *)message {
    NSAlert *alert = [[NSAlert alloc] init];
    alert.messageText = @"隔空绘画无法启动";
    alert.informativeText = message;
    [alert addButtonWithTitle:@"关闭"];
    [NSApp activateIgnoringOtherApps:YES];
    [alert runModal];
    [NSApp terminate:nil];
}
- (void)launchPainter {
    NSString *root = [[[NSBundle mainBundle] bundlePath] stringByDeletingLastPathComponent];
    NSString *python = [root stringByAppendingPathComponent:@".venv/bin/python"];
    if (![[NSFileManager defaultManager] isExecutableFileAtPath:python]) {
        [self fail:@"请先在项目目录运行 ./setup.sh 安装依赖。"];
        return;
    }
    NSString *cache = [root stringByAppendingPathComponent:@".cache"];
    [[NSFileManager defaultManager] createDirectoryAtPath:cache withIntermediateDirectories:YES attributes:nil error:nil];
    NSString *log = [cache stringByAppendingPathComponent:@"run.log"];
    [[NSFileManager defaultManager] createFileAtPath:log contents:nil attributes:nil];
    NSFileHandle *output = [NSFileHandle fileHandleForWritingAtPath:log];
    NSTask *task = [[NSTask alloc] init];
    task.executableURL = [NSURL fileURLWithPath:python];
    task.currentDirectoryURL = [NSURL fileURLWithPath:root];
    NSMutableArray *args = [NSMutableArray arrayWithObject:[root stringByAppendingPathComponent:@"run_app.py"]];
    for (NSString *arg in [[[NSProcessInfo processInfo] arguments] subarrayWithRange:NSMakeRange(1, [[[NSProcessInfo processInfo] arguments] count] - 1)]) {
        if (![arg hasPrefix:@"-psn_"]) [args addObject:arg];
    }
    task.arguments = args;
    NSMutableDictionary *env = [[[NSProcessInfo processInfo] environment] mutableCopy];
    env[@"MPLCONFIGDIR"] = [cache stringByAppendingPathComponent:@"matplotlib"];
    env[@"XDG_CACHE_HOME"] = cache;
    env[@"PYTHONUNBUFFERED"] = @"1";
    task.environment = env;
    task.standardOutput = output;
    task.standardError = output;
    __weak PainterDelegate *weakSelf = self;
    task.terminationHandler = ^(NSTask *finished) {
        dispatch_async(dispatch_get_main_queue(), ^{
            if (finished.terminationStatus != 0) {
                [weakSelf fail:[NSString stringWithFormat:@"程序退出，代码 %d。详情见 %@。", finished.terminationStatus, log]];
            } else {
                [NSApp terminate:nil];
            }
        });
    };
    self.task = task;
    NSError *error = nil;
    if (![task launchAndReturnError:&error]) [self fail:error.localizedDescription];
}
- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    if ([[[NSProcessInfo processInfo] arguments] containsObject:@"--no-camera"]) {
        [self launchPainter];
        return;
    }
    AVAuthorizationStatus status = [AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeVideo];
    if (status == AVAuthorizationStatusAuthorized) {
        [self launchPainter];
    } else if (status == AVAuthorizationStatusNotDetermined) {
        [NSApp activateIgnoringOtherApps:YES];
        [AVCaptureDevice requestAccessForMediaType:AVMediaTypeVideo completionHandler:^(BOOL granted) {
            dispatch_async(dispatch_get_main_queue(), ^{
                if (granted) [self launchPainter];
                else [self fail:@"需要摄像头权限。请在系统设置 → 隐私与安全性 → 摄像头中允许 Air Painter，然后重新启动。"];
            });
        }];
    } else {
        [self fail:@"摄像头权限被拒绝或受到限制。请在系统设置 → 隐私与安全性 → 摄像头中允许 Air Painter，然后重新启动。"];
    }
}
- (NSApplicationTerminateReply)applicationShouldTerminate:(NSApplication *)sender {
    if (self.task.running) [self.task terminate];
    return NSTerminateNow;
}
@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];
        PainterDelegate *delegate = [[PainterDelegate alloc] init];
        app.delegate = delegate;
        [app run];
    }
    return 0;
}
