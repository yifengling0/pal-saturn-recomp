// ROM-free SDL3 capability probe. No game, BIOS, account, or device writes.
#include <SDL3/SDL.h>
#include <stdio.h>
#include <stdlib.h>

static const char *safe(const char *s) { return s ? s : "(none)"; }
int main(int argc, char **argv) {
    const unsigned seconds = argc > 1 ? (unsigned)atoi(argv[1]) : 30;
    setvbuf(stdout, NULL, _IOLBF, 0);
    printf("SDL_VERSION=%d.%d.%d\n", SDL_VERSIONNUM_MAJOR(SDL_GetVersion()), SDL_VERSIONNUM_MINOR(SDL_GetVersion()), SDL_VERSIONNUM_MICRO(SDL_GetVersion()));
    for (int i = 0; i < SDL_GetNumVideoDrivers(); ++i) printf("VIDEO_AVAILABLE=%s\n", SDL_GetVideoDriver(i));
    if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS)) { fprintf(stderr,"VIDEO_INIT_FAIL=%s\n", SDL_GetError()); return 1; }
    printf("VIDEO_DRIVER=%s\n", safe(SDL_GetCurrentVideoDriver()));
    SDL_Window *window = NULL; SDL_Renderer *renderer = NULL;
    if (!SDL_CreateWindowAndRenderer("PAL Saturn: ROM-free SDL3 environment probe", 800, 480, 0, &window, &renderer)) {
        fprintf(stderr,"WINDOW_RENDERER_FAIL=%s\n", SDL_GetError()); SDL_Quit(); return 2;
    }
    printf("WINDOW_OK=1\nRENDERER=%s\n", safe(SDL_GetRendererName(renderer)));
    SDL_AudioStream *stream = NULL;
    if (SDL_InitSubSystem(SDL_INIT_AUDIO)) {
        int count = 0; SDL_AudioDeviceID *ids = SDL_GetAudioPlaybackDevices(&count);
        printf("AUDIO_DRIVER=%s\nAUDIO_PLAYBACK_COUNT=%d\n", safe(SDL_GetCurrentAudioDriver()), count);
        for (int i=0; i<count; ++i) printf("AUDIO_PLAYBACK=%s\n", safe(SDL_GetAudioDeviceName(ids[i])));
        SDL_free(ids);
        SDL_AudioSpec spec = {SDL_AUDIO_F32, 2, 48000};
        stream = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, NULL, NULL);
        if (stream) {
            float silence[9600] = {0};
            const bool queued = SDL_PutAudioStreamData(stream, silence, sizeof silence);
            const bool resumed = SDL_ResumeAudioStreamDevice(stream);
            printf("AUDIO_STREAM_OPEN=1\nAUDIO_SILENCE_QUEUED=%d\nAUDIO_STREAM_RESUMED=%d\n", queued, resumed);
        } else printf("AUDIO_STREAM_OPEN=0\nAUDIO_STREAM_ERROR=%s\n", SDL_GetError());
    } else printf("AUDIO_INIT_FAIL=%s\n", SDL_GetError());
    if (SDL_InitSubSystem(SDL_INIT_GAMEPAD)) {
        int count = 0; SDL_JoystickID *ids = SDL_GetGamepads(&count);
        printf("GAMEPAD_COUNT=%d\n", count); SDL_free(ids);
    } else printf("GAMEPAD_INIT_FAIL=%s\n", SDL_GetError());
    bool run = true, present_failed = false; unsigned frames = 0; Uint64 start = SDL_GetTicks();
    while (run && SDL_GetTicks() - start < seconds * 1000u) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_EVENT_QUIT) run = false;
            if (e.type == SDL_EVENT_KEY_DOWN) { printf("KEYDOWN=%s\n", safe(SDL_GetKeyName(e.key.key))); if(e.key.key == SDLK_ESCAPE) run=false; }
            if (e.type == SDL_EVENT_MOUSE_BUTTON_DOWN) printf("MOUSE_BUTTON_DOWN=%u\n", e.button.button);
        }
        SDL_SetRenderDrawColor(renderer, 18, 22, 31, 255); SDL_RenderClear(renderer);
        SDL_FRect r = {40.0f + (float)((SDL_GetTicks()-start)%1500u)/3.0f, 180, 150, 100};
        SDL_SetRenderDrawColor(renderer, 57, 196, 137, 255); SDL_RenderFillRect(renderer, &r);
        SDL_SetRenderDrawColor(renderer, 239, 243, 250, 255);
        SDL_SetRenderScale(renderer, 2.0f, 2.0f);
        SDL_RenderDebugText(renderer, 20, 20, "PAL SATURN - SDL3 ENVIRONMENT PROBE");
        SDL_RenderDebugText(renderer, 20, 38, "Synthetic graphics only. No ROM or BIOS.");
        SDL_RenderDebugText(renderer, 20, 170, "ESC: close | Keyboard events are logged");
        SDL_RenderDebugText(renderer, 20, 190, safe(SDL_GetCurrentVideoDriver()));
        SDL_RenderDebugText(renderer, 20, 205, safe(SDL_GetRendererName(renderer)));
        SDL_SetRenderScale(renderer, 1.0f, 1.0f);
        if (frames == 15 && argc > 2) {
            SDL_Surface *surface = SDL_RenderReadPixels(renderer, NULL);
            if (surface) { printf("FRAMEBUFFER_SAVED=%d\n", SDL_SaveBMP(surface, argv[2])); SDL_DestroySurface(surface); }
            else printf("FRAMEBUFFER_ERROR=%s\n", SDL_GetError());
        }
        if (!SDL_RenderPresent(renderer)) { printf("PRESENT_FAIL=%s\n", SDL_GetError()); present_failed=true; break; }
        ++frames; SDL_Delay(16);
    }
    printf("FRAMES_PRESENTED=%u\nELAPSED_MS=%llu\n", frames, (unsigned long long)(SDL_GetTicks()-start));
    if(stream) SDL_DestroyAudioStream(stream);
    SDL_DestroyRenderer(renderer); SDL_DestroyWindow(window); SDL_Quit();
    return present_failed ? 4 : (frames ? 0 : 3);
}
