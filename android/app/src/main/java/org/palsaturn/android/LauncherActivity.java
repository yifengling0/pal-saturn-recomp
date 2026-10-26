package org.palsaturn.android;

import android.app.Activity;
import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import android.widget.*;
import java.io.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

/** Offline-only SAF launcher. No storage permissions and no telemetry. */
public final class LauncherActivity extends Activity {
    private TextView status;
    private Button files, folder, play, cancel;
    private final AtomicBoolean cancelled=new AtomicBoolean();
    private volatile boolean busy;
    private static final AtomicBoolean cleaned=new AtomicBoolean();
    private File home;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        home=new File(getFilesDir(),"resources");
        if(cleaned.compareAndSet(false,true))DiscImport.cleanup(home);
        LinearLayout list=new LinearLayout(this); list.setOrientation(LinearLayout.VERTICAL);
        int p=(int)(20*getResources().getDisplayMetrics().density); list.setPadding(p,p,p,p);
        TextView title=new TextView(this); title.setText("仙剑奇侠传 · 土星版\nAndroid ARM64 测试版"); title.setTextSize(23); list.addView(title);
        TextView help=new TextView(this); help.setText("请自备合法原盘 T-37401H V1.000。导入包含CUE及全部BIN音轨的文件夹，或一次多选全部文件。跨子目录请使用文件夹导入。\n资源复制到应用私有目录；更换资源不会删除存档。卸载应用会删除私有数据，请先导出存档。\n游戏支持触屏和手柄；返回键打开游戏菜单。"); list.addView(help);
        files=button(list,"选择 CUE + 全部 BIN",()->choose(false));
        folder=button(list,"选择资源文件夹",()->choose(true));
        play=button(list,"开始游戏",this::launch);
        cancel=button(list,"取消当前导入",()->{cancelled.set(true); status.setText("正在取消…");}); cancel.setEnabled(false);
        button(list,"导出存档 ZIP（内置存档及记忆卡）",()->{ if(new File(getFilesDir(),"saves/backup.bin").isFile()) startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("application/zip").putExtra(Intent.EXTRA_TITLE,"pal-saturn-saves.zip"),3); else status.setText("尚无存档，请在游戏中存档并退出后导出"); });
        status=new TextView(this); list.addView(status); ScrollView scroll=new ScrollView(this); scroll.setFitsSystemWindows(true); scroll.addView(list); setContentView(scroll);
        refresh();
    }
    private Button button(LinearLayout list,String text,Runnable action) { Button b=new Button(this); b.setText(text); b.setOnClickListener(v->action.run()); list.addView(b); return b; }
    private void refresh() { try { boolean found=DiscImport.current(home)!=null; play.setEnabled(found&&!busy); if(!busy)status.setText(found?"资源已就绪，可以启动":"尚未导入资源"); } catch(IOException e) {status.setText(e.getMessage());play.setEnabled(false);} }
    private void choose(boolean tree) {
        if(busy)return;
        Intent i=tree?new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE):new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*").putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true);
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION); startActivityForResult(i,tree?2:1);
    }
    private DiscImport.Source source(Uri uri,String name,long size) { return new DiscImport.Source() {
        public String name(){return name;} public long size(){return size;}
        public InputStream open() throws IOException { InputStream i=getContentResolver().openInputStream(uri); if(i==null)throw new IOException("无法读取："+name); return i; }
    }; }
    private DiscImport.Source document(Uri uri) throws IOException {
        try(Cursor c=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE},null,null,null)) {
            if(c==null||!c.moveToFirst())throw new IOException("文档不可读取");
            return source(uri,c.getString(0),c.isNull(1)?-1:c.getLong(1));
        }
    }
    private void walk(Uri tree,String id,String prefix,List<DiscImport.Source> out,int depth) throws IOException {
        DiscImport.check(cancelled); if(depth>16||out.size()>512)throw new IOException("资源目录过深或文件过多，请单独整理一张光盘");
        Uri children=DocumentsContract.buildChildDocumentsUriUsingTree(tree,id);
        String[] cols={DocumentsContract.Document.COLUMN_DOCUMENT_ID,DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE,DocumentsContract.Document.COLUMN_SIZE};
        try(Cursor c=getContentResolver().query(children,cols,null,null,null)) {
            if(c==null)throw new IOException("无法读取所选文件夹");
            while(c.moveToNext()) {
                String child=c.getString(0),name=prefix+c.getString(1);
                if(DocumentsContract.Document.MIME_TYPE_DIR.equals(c.getString(2)))walk(tree,child,name+"/",out,depth+1);
                else out.add(source(DocumentsContract.buildDocumentUriUsingTree(tree,child),name,c.isNull(3)?-1:c.getLong(3)));
            }
        }
    }
    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);
        if(result!=RESULT_OK||data==null) { if(!busy)refresh(); return; }
        if(request==3) {
            try(RandomAccessFile g=new RandomAccessFile(new File(home,"resource.lock"),"rw");java.nio.channels.FileLock lock=g.getChannel().tryLock()) {
                if(lock==null)throw new IOException("请先从游戏菜单退出，再导出存档");
                try(OutputStream stream=getContentResolver().openOutputStream(data.getData(),"wt")) {
                    if(stream==null)throw new IOException("目标不可写");
                    try(java.util.zip.ZipOutputStream out=new java.util.zip.ZipOutputStream(stream)) {
                        for(String name:new String[]{"backup.bin","cartridge.bin","settings.ini"}) {File f=new File(getFilesDir(),"saves/"+name);if(!f.isFile())continue;out.putNextEntry(new java.util.zip.ZipEntry(name));try(InputStream in=new FileInputStream(f)){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);}out.closeEntry();}
                    }
                }
                status.setText("存档ZIP已导出；包括已存在的内置存档、记忆卡和设置");
            }catch(Exception e){status.setText("导出失败："+e.getMessage());}return;
        }
        if(request!=1&&request!=2||busy)return;
        busy=true;cancelled.set(false);files.setEnabled(false);folder.setEnabled(false);play.setEnabled(false);cancel.setEnabled(true);status.setText("检查资源…");
        new Thread(()->{
            String message;
            try {
                List<DiscImport.Source> entries=new ArrayList<>();
                if(request==2) walk(data.getData(),DocumentsContract.getTreeDocumentId(data.getData()),"",entries,0);
                else if(data.getClipData()!=null)for(int n=0;n<data.getClipData().getItemCount();n++)entries.add(document(data.getClipData().getItemAt(n).getUri()));
                else entries.add(document(data.getData()));
                final long[] last={0};
                DiscImport.run(home,entries,cancelled,label->{ long now=System.currentTimeMillis();if(now-last[0]>150){last[0]=now;runOnUiThread(()->status.setText(label));} });
                message="资源导入成功；原文件和存档保持不变";
            } catch(Exception e) {message="导入未完成："+e.getMessage()+"\n可重新选择重试；原资源和存档未改变。";}
            final String done=message;
            runOnUiThread(()->{busy=false;files.setEnabled(true);folder.setEnabled(true);cancel.setEnabled(false);refresh();status.setText(done);});
        },"disc-import").start();
    }
    private void launch() {
        try {
            try(RandomAccessFile g=new RandomAccessFile(new File(home,"resource.lock"),"rw");java.nio.channels.FileLock lock=g.getChannel().tryLock()) {
                if(lock==null)throw new IOException("游戏已在运行，请从最近任务返回游戏，或先从游戏菜单退出");
            }
            File cue=DiscImport.current(home);if(cue==null)throw new IOException("请先导入完整资源");
            File saves=new File(getFilesDir(),"saves");saves.mkdirs();
            File logs=new File(getFilesDir(),"logs");logs.mkdirs();
            String[] args={"--cue",cue.getAbsolutePath(),"--save",new File(saves,"backup.bin").getAbsolutePath(),"--settings",new File(saves,"settings.ini").getAbsolutePath(),"--out",logs.getAbsolutePath(),"--log",new File(logs,"runtime.log").getAbsolutePath(),"--cart",new File(saves,"cartridge.bin").getAbsolutePath(),"--clock","1998-11-01T12:00:00","--launcher"};
            startActivity(new Intent(this,GameActivity.class).putExtra("args",args));
        }catch(Exception e){status.setText("启动失败："+e.getMessage());}
    }
    @Override protected void onDestroy(){cancelled.set(true);super.onDestroy();}
}
