package parsing

import (
	"github.com/combaine/combaine/common"
	"github.com/combaine/combaine/common/servicecacher"
)

type Parser interface {
	Parse(tid string, parsername string, data []byte) ([]byte, error)
}

type parser struct {
	app servicecacher.Service
}

func (p *parser) Parse(tid string, parsername string, data []byte) (z []byte, err error) {
	taskToParser, err := common.Pack([]interface{}{tid, parsername, data})
	if err != nil {
		return
	}

	res := <-p.app.Call("enqueue", "parse", taskToParser)
	if res == nil {
		return nil, common.ErrAppCall
	}
	if err = res.Err(); err != nil {
		return
	}

	if err = res.Extract(&z); err != nil {
		return
	}
	return
}

func GetParser(cacher servicecacher.Cacher) (p Parser, err error) {
	app, err := cacher.Get(common.PARSINGAPP)
	if err != nil {
		return
	}
	p = &parser{app: app}
	return
}
