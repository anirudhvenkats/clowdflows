from django.shortcuts import render

def MUSE_filter_integers(request,input_dict,output_dict,widget):
    return render(request, 'interactions/MUSE_filter_integers.html',{'widget':widget,'intList':input_dict['intList']})