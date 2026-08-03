%{
int yylex(void);
void yyerror(const char *message) {(void)message;}
%}
%%
input: ;
%%
