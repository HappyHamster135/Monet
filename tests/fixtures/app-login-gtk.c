/* Real GTK controls in a Flatpak runtime; all values are synthetic.
 * Use only GTK3's stable C ABI, so this fixture needs no SDK installation. */
#include <stdlib.h>
#include <string.h>
typedef void Widget;
extern void gtk_init(int*,char***), gtk_main(void), gtk_widget_show_all(Widget*), gtk_window_present(Widget*), gtk_widget_grab_focus(Widget*), gtk_widget_hide(Widget*);
extern Widget *gtk_window_new(int), *gtk_box_new(int,int), *gtk_entry_new(void), *gtk_label_new_with_mnemonic(const char*), *gtk_button_new_with_label(const char*);
extern void gtk_window_set_title(Widget*,const char*), gtk_container_add(Widget*,Widget*), gtk_box_pack_start(Widget*,Widget*,int,int,unsigned), gtk_label_set_mnemonic_widget(Widget*,Widget*), gtk_entry_set_text(Widget*,const char*), gtk_entry_set_visibility(Widget*,int), gtk_editable_set_editable(Widget*,int);
extern const char *gtk_entry_get_text(Widget*);
extern unsigned g_timeout_add(unsigned,int(*)(void*),void*);
extern unsigned long g_signal_connect_data(void*,const char*,void(*)(void),void*,void*,int);
extern void g_signal_emit_by_name(void*,const char*,...);
static Widget *box,*user,*password,*button;
static const char *mode;
static int submitted;
static Widget *field(const char *label,const char *value) {
    Widget *entry=gtk_entry_new(),*caption=gtk_label_new_with_mnemonic(label);
    gtk_entry_set_text(entry,value);gtk_label_set_mnemonic_widget(caption,entry);
    gtk_box_pack_start(box,caption,0,0,0);gtk_box_pack_start(box,entry,0,0,0);return entry;
}
static void submit(void) { submitted=1;gtk_widget_hide(password);gtk_widget_hide(button); }
static int focus(void *data) {gtk_widget_grab_focus(data);return 0;}
static int type(void *unused) {gtk_entry_set_text(password,"synthetic-fill-only");return 0;}
static int click(void *unused) {g_signal_emit_by_name(button,"clicked");return 0;}
static int verify(void *unused) {
    int good=!strcmp(mode,"save") ? submitted : !submitted && !strcmp(gtk_entry_get_text(user),"fixture@example.invalid") && !strcmp(gtk_entry_get_text(password),"synthetic-fill-only");
    exit(good?0:1);
}
int main(int argc,char **argv) {
    mode=argc>1?argv[1]:"fill";gtk_init(&argc,&argv);
    Widget *window=gtk_window_new(0);gtk_window_set_title(window,"Synthetic sandbox login");
    box=gtk_box_new(1,12);gtk_container_add(window,box);
    field("_Server","server.example.invalid");
    user=field("_Username",!strcmp(mode,"save")||!strcmp(mode,"readonly")?"fixture@example.invalid":"");
    if(!strcmp(mode,"readonly"))gtk_editable_set_editable(user,0);
    password=field("_Password","");gtk_entry_set_visibility(password,0);
    button=gtk_button_new_with_label("Sign in");gtk_box_pack_start(box,button,0,0,0);
    g_signal_connect_data(button,"clicked",submit,0,0,0);
    gtk_widget_show_all(window);gtk_window_present(window);
    g_timeout_add(1000,focus,password);
    if(!strcmp(mode,"save")){g_timeout_add(1300,type,0);g_timeout_add(1700,focus,button);g_timeout_add(1900,click,0);}
    g_timeout_add(3200,verify,0);gtk_main();return 2;
}
