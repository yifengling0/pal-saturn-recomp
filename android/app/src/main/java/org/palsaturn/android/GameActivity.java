package org.palsaturn.android;

import org.libsdl.app.SDLActivity;
import android.os.Process;
import android.os.Bundle;
import android.widget.Toast;
import android.view.KeyEvent;
import java.io.*;
import java.nio.channels.*;

/** SDL owns touch, gamepads, audio focus and the pause/menu lifecycle. */
public final class GameActivity extends SDLActivity {
    private RandomAccessFile guard;
    private FileLock lock;
    @Override public void loadLibraries() {
        if(lock==null||!lock.isValid())throw new UnsatisfiedLinkError("资源正在使用，启动已安全取消");
        super.loadLibraries();
    }
    @Override protected void onCreate(Bundle state) {
        try {
            guard=new RandomAccessFile(new File(getFilesDir(),"resources/resource.lock"),"rw");
            lock=guard.getChannel().tryLock(0,Long.MAX_VALUE,true);
            if(lock==null)throw new IOException("资源正在导入，请等待完成后重试");
        }catch(Exception e){super.onCreate(state);Toast.makeText(this,e.getMessage(),Toast.LENGTH_LONG).show();finish();return;}
        super.onCreate(state);
    }
    @Override protected String[] getLibraries() { return new String[]{"SDL3", "main"}; }
    @Override protected String[] getArguments() {
        String[] args=getIntent().getStringArrayExtra("args");
        // Resolve after acquiring the cross-process lock, not from a stale launcher intent.
        try {File cue=DiscImport.current(new File(getFilesDir(),"resources"));if(cue!=null)for(int i=0;i+1<args.length;i++)if(args[i].equals("--cue"))args[i+1]=cue.getAbsolutePath();}catch(IOException ignored){}
        return args;
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        if(event.getKeyCode()!=KeyEvent.KEYCODE_BACK)return super.dispatchKeyEvent(event);
        if(event.getAction()==KeyEvent.ACTION_UP&&(event.getDevice()==null||event.getDevice().isVirtual()))onBackPressed();
        return true;
    }
    @Override public void onBackPressed() {
        // Navigation back/gesture opens the guest menu, never destroys SDL mid-save.
        if(lock!=null&&lock.isValid()&&!mBrokenLibraries){onNativeKeyDown(KeyEvent.KEYCODE_BACK);onNativeKeyUp(KeyEvent.KEYCODE_BACK);}
    }
    @Override protected void onDestroy() {
        super.onDestroy();
        try {if(lock!=null)lock.release();if(guard!=null)guard.close();}catch(IOException ignored){}
        // Separate :game process: a new launch must not inherit the guest's global state.
        Process.killProcess(Process.myPid());
    }
}
